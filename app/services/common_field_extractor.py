import re
class CommonFieldExtractor:
    def extract(self,text:str)->dict:
        def m(p):
            x=re.search(p,text,re.I); return x.group(1).strip() if x else None
        return {'patient_name':m(r'(?:Patient Name|Name|نام بیمار)[:\s]+([^\n]+)'),'national_id':m(r'(?:National ID|کد ملی)[:\s]+([0-9]{6,12})'),'date_of_test_or_report':m(r'(?:Date|Report Date)[:\s]+([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})'),'test_or_report_name':m(r'(?:Test|Report|Exam)[:\s]+([^\n]+)'),'center_name':m(r'(?:Center|Laboratory|Hospital|Clinic)[:\s]+([^\n]+)')}
