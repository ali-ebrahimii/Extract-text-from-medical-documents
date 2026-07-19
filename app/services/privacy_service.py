from __future__ import annotations
import hashlib, re, unicodedata

def normalize_persian_text(text: str | None) -> str:
    if not text: return ''
    text = unicodedata.normalize('NFKC', text)
    table = str.maketrans({'ك':'ک','ي':'ی','ھ':'ه','ة':'ه','أ':'ا','إ':'ا','ٱ':'ا','ؤ':'و','ئ':'ی'})
    text = text.translate(table)
    text = text.replace('مھلا','مهلا').replace('طھران','تهران').replace('طهران','تهران')
    text = re.sub(r'[\t\r]+',' ', text)
    text = re.sub(r'[:：|]+', ':', text)
    return re.sub(r'\s+',' ', text).strip()

def validate_iranian_national_id(code: str | None) -> bool:
    if not code or not re.fullmatch(r'\d{10}', code): return False
    if len(set(code)) == 1: return False
    check = int(code[9]); s = sum(int(code[i]) * (10 - i) for i in range(9)); r = s % 11
    return (r < 2 and check == r) or (r >= 2 and check == 11 - r)

def mask_national_id(code: str | None) -> str | None:
    if not code: return None
    return f'{code[:3]}****{code[-3:]}' if len(code) >= 6 else '*' * len(code)

def hash_sha256(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest() if value else None
