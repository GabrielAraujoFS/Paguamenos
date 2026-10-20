import json
from pathlib import Path
from app.schemas import Product
from app.schemas.configuration import parse_rules
DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
class Catalog:
    def __init__(self, path=DATA_DIR / 'products.json'):
        self.path = path
    def all(self):
        products = [Product.model_validate(p) for p in json.loads(self.path.read_text(encoding='utf-8'))]
        if len({p.id for p in products}) != len(products):
            raise ValueError('IDs duplicados no catálogo.')
        return products
    def get(self, product_id):
        return next((p for p in self.all() if p.id == product_id), None)
def load_rules(path=DATA_DIR / 'brand_rules.json'):
    return parse_rules(json.loads(path.read_text(encoding='utf-8'))).model_dump(mode='json')
