from sqlalchemy import select
from .models import APIUsage

def record(db,uid,feature,model,usage=None,status='success'):
    if not uid:return
    incoming=usage.get('input_tokens',0) if isinstance(usage,dict) else getattr(usage,'input_tokens',0) if usage else 0
    outgoing=usage.get('output_tokens',0) if isinstance(usage,dict) else getattr(usage,'output_tokens',0) if usage else 0
    db.add(APIUsage(user_id=uid,feature=feature,model=model,status=status,input_tokens=int(incoming),output_tokens=int(outgoing)))
    db.commit()

def summary(db,uid):
    groups={}
    for row in db.scalars(select(APIUsage).where(APIUsage.user_id==uid)):
        item=groups.setdefault(row.feature,{'calls':0,'failures':0,'input_tokens':0,'output_tokens':0})
        item['calls']+=1;item['failures']+=row.status!='success';item['input_tokens']+=row.input_tokens;item['output_tokens']+=row.output_tokens
    return {'features':groups,'billing_note':'Token/call counts only; no billing estimate or free quota is implied. Failed calls may have unreported provider usage.'}
