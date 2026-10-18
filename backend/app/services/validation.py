import hashlib
import json
from decimal import Decimal, InvalidOperation
from app.schemas import Severity, ValidationResult

def fingerprint(content, product, rules):
    payload = dict(content=content, product=product.model_dump(mode='json') if product else None, rules=rules)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def validate_content(content, product, rules):
    results=[]
    def check(code,field,passed,message):
        results.append(ValidationResult(rule_code=code,severity=Severity.CRITICAL,field=field,passed=bool(passed),message=message))
    check('PRODUCT_EXISTS','product_id',product is not None,'Produto deve existir no catálogo.')
    try:
        price=Decimal(str(content.get('price')))
        matches=price.is_finite() and product is not None and price==product.price
    except (InvalidOperation,ValueError,TypeError):
        matches=False
    check('PRICE_MATCH','price',matches,'Preço deve corresponder ao catálogo.')
    for field,attribute,code in [('product_name','name','PRODUCT_NAME_MATCH'),('authorized_offer','authorized_offer','OFFER_MATCH')]:
        check(code,field,product is not None and content.get(field)==getattr(product,attribute),'Dados autorizados do catálogo.')
    for field in rules['required_fields']:
        value=content.get(field)
        check('REQUIRED_FIELD',field,value is not None and bool(str(value).strip()),'Campo obrigatório.')
    channel=content.get('channel')
    check('CHANNEL_ALLOWED','channel',channel in rules['allowed_channels'],'Canal permitido.')
    for field,limit in rules['character_limits'].get(channel,{}).items():
        check('CHARACTER_LIMIT',field,len(str(content.get(field) or ''))<=limit,f'Limite de {limit} caracteres.')
    for field,texts in rules['required_information'].items():
        for text in texts:
            check('REQUIRED_INFORMATION',field,text in str(content.get(field) or ''),f'Informação obrigatória: {text}')
    return results
def successful(results):
    return all(r.passed for r in results if r.severity==Severity.CRITICAL)
