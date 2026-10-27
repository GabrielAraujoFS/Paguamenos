"""Publication preferences never replace internal commercial data or brand rules."""
import re
from decimal import Decimal


def has_price(text):
    return bool(re.search(r'r\$|\$|€|£|\b(?:reais|brl)\b|\b\d+[.,]\d{2}\b',
                          str(text or ''), re.IGNORECASE))


def published_texts(content):
    texts = {key: content.get(key) for key in ('title', 'subtitle', 'cta', 'disclaimer', 'product_name')}
    offer = str(content.get('authorized_offer') or '')
    if content.get('show_price', True):
        texts['price'] = f"R$ {Decimal(str(content['price'])):.2f}".replace('.', ',')
    if content.get('show_price', True) or not (has_price(offer) or re.search(r'\bpre[cç]o\b', offer, re.IGNORECASE)):
        texts['offer'] = offer
    return texts
