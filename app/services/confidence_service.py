class ConfidenceService:
    def calculate(self,ocr_confidence:float, document_type_confidence:float, common:dict, specific)->float:
        present=sum(v is not None and v!='' for v in common.values())/max(1,len(common))
        spec=.5
        if isinstance(specific,list): spec=min(1,len(specific)/3)
        elif isinstance(specific,dict): spec=sum(v is not None and v!='' for k,v in specific.items() if k!='confidence')/max(1,len(specific)-1)
        return round((ocr_confidence*.35+document_type_confidence*.25+present*.2+spec*.2),3)
