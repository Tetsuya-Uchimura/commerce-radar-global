from datetime import date
from decimal import Decimal,InvalidOperation
from pydantic import BaseModel,Field,ConfigDict
from fastapi import HTTPException
from .models import Purchase
from .costs import EXPONENTS

class PurchaseInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    purchased_at:date
    merchant_name:str=Field(min_length=1,max_length=100)
    country_code:str=Field(pattern='^[A-Z]{2}$')
    product_name:str=Field(min_length=1,max_length=150)
    category:str=Field(min_length=1,max_length=40)
    quantity:int=Field(ge=1,le=1000)
    price:str=Field(max_length=30)
    currency:str=Field(pattern='^[A-Z]{3}$')
    notes:str=Field(default='',max_length=1000)

def validated(body):
    if not body.merchant_name.strip() or not body.product_name.strip():raise HTTPException(422,'Product and merchant names cannot be blank.')
    if body.purchased_at>date.today():raise HTTPException(422,'Purchase date cannot be in the future.')
    if body.currency not in EXPONENTS:raise HTTPException(422,'Unsupported purchase currency.')
    from .seed import CATEGORIES
    if body.category not in CATEGORIES+['Unknown']:raise HTTPException(422,'Choose a known category or Unknown.')
    try:
        amount=Decimal(body.price)
        minor=amount.scaleb(EXPONENTS[body.currency])
        if not amount.is_finite() or amount<=0 or minor!=minor.to_integral_value() or minor>100000000:raise ValueError()
    except (ValueError,InvalidOperation):raise HTTPException(422,'Price must be positive with valid currency decimal places.')
    fields=body.model_dump(exclude={'price'});fields['amount']=int(minor)*body.quantity
    return fields

def editable(db,uid,pid):
    row=db.get(Purchase,pid)
    if row is None or row.user_id!=uid or row.deleted:raise HTTPException(404,'Purchase not found.')
    if row.source not in ('synthetic_global','user_provided'):raise HTTPException(403,'Completed payment histories are read-only.')
    return row
