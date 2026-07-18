from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import re, fitz, pytesseract
from PIL import Image, ImageOps, ImageFilter

@dataclass
class OCRCandidateV2:
    text: str
    words: list[dict[str,Any]]=field(default_factory=list)
    visual_lines: list[str]=field(default_factory=list)
    sections: dict[str,str]=field(default_factory=dict)
    confidence: float=0.0
    layout_status: str='empty_text'
    score_details: dict[str,Any]=field(default_factory=dict)
    variant_name: str|None=None
    psm: int|None=None
    lang: str|None=None

MED=['WBC','RBC','HGB','AST','ALT','Creatinine','Glucose','کد ملی','آزمایشگاه','Patient']
class OCRLayoutService:
    def extract(self,path:str,mime_type:str|None=None)->OCRCandidateV2:
        if (mime_type or '').lower().startswith('application/pdf') or path.lower().endswith('.pdf'):
            cand=self._pdf_text(path)
            if cand.text.strip(): return cand
        return self._image_ocr(path)
    def _status(self,text,conf):
        if not text.strip(): return 'empty_text'
        if len(text)<30 and re.search(r'culture|growth',text,re.I): return 'usable_short_culture_text'
        bad=sum(1 for c in text if ord(c)>127 and not ('\u0600'<=c<='\u06ff'))
        if bad/max(len(text),1)>.25: return 'gibberish_or_bad_layout_text'
        return 'good_layout_text' if conf>=70 or len(text)>200 else 'usable_noisy_layout_text'
    def _score(self,text,conf):
        kw=sum(1 for k in MED if k.lower() in text.lower()); nums=len(re.findall(r'\d+(?:\.\d+)?',text)); table=sum(1 for l in text.splitlines() if len(re.findall(r'\s{2,}|\t|\|',l))>=1)
        gib=1 if self._status(text,conf)=='gibberish_or_bad_layout_text' else 0
        return {'ocr_confidence':conf,'medical_keyword_count':kw,'numeric_result_count':nums,'table_like_line_count':table,'gibberish_penalty':gib,'score':conf+kw*10+nums+table*3-gib*100}
    def _pdf_text(self,path):
        doc=fitz.open(path); pages=[]
        for page in doc: pages.append(page.get_text('text'))
        text='\n'.join(pages); conf=95.0 if len(text.strip())>30 else 0.0
        return OCRCandidateV2(text=text,visual_lines=text.splitlines(),confidence=conf,layout_status=self._status(text,conf),score_details=self._score(text,conf),variant_name='pdf_text_layer',lang='embedded')
    def _image_ocr(self,path):
        img=Image.open(path); variants=[('original',img),('grayscale_autocontrast',ImageOps.autocontrast(ImageOps.grayscale(img))),('light_sharpen',img.filter(ImageFilter.SHARPEN))]
        best=OCRCandidateV2(text='',variant_name='original')
        for vname,im in variants:
            for rot in (0,90,180,270):
                rim=im.rotate(rot, expand=True) if rot else im
                for psm in (4,6,11,12):
                    for lang in ('eng+fas','eng'):
                        try: data=pytesseract.image_to_data(rim,lang=lang,config=f'--psm {psm}',output_type=pytesseract.Output.DICT)
                        except Exception: continue
                        words=[]; toks=[]; confs=[]
                        for i,w in enumerate(data.get('text',[])):
                            if not w.strip(): continue
                            c=float(data['conf'][i]) if str(data['conf'][i]).replace('.','',1).lstrip('-').isdigit() else -1
                            toks.append(w); confs.append(max(c,0)); words.append({'text':w,'x':data['left'][i],'y':data['top'][i],'w':data['width'][i],'h':data['height'][i],'confidence':c})
                        lines=self._reconstruct(words); text='\n'.join(lines) if lines else ' '.join(toks); conf=sum(confs)/len(confs) if confs else 0
                        cand=OCRCandidateV2(text=text,words=words,visual_lines=lines,confidence=conf,layout_status=self._status(text,conf),score_details=self._score(text,conf),variant_name=f'{vname}_rot{rot}',psm=psm,lang=lang)
                        if cand.score_details['score']>best.score_details.get('score',-999): best=cand
        return best
    def _reconstruct(self,words):
        rows=[]
        for w in sorted(words,key=lambda x:(x['y'],x['x'])):
            for row in rows:
                if abs(row[0]['y']-w['y']) <= max(row[0]['h'],w['h'])*.7: row.append(w); break
            else: rows.append([w])
        return [' '.join(x['text'] for x in sorted(r,key=lambda z:z['x'])) for r in rows]
