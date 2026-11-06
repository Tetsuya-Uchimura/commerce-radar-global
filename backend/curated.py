"""Small, dated real price observations, always separate from fictional demo data."""
import json,re
from pathlib import Path
FILE=Path(__file__).with_name('fixtures')/'curated_products.json'
def candidates(query,currency=None):
    if not FILE.exists():return []
    data=json.loads(FILE.read_text(encoding='utf-8'));tokens=set(re.findall(r'[a-z]{4,}',query.lower()))
    return [dict(p,curated_snapshot=True) for p in data.get('items',[])
        if (not currency or p.get('currency')==currency) and any(t in (p['name']+' '+p.get('category','')).lower() for t in tokens)]
