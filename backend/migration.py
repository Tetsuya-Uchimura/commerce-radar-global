"""Read-only, idempotent import of legacy consumer transactions. Old DB stays intact."""
from pathlib import Path
import sqlite3
from sqlalchemy import select
from .models import MigrationState, User, InterestProfile, Purchase
from .config import ROOT

CATEGORY_MAP={'Food & Beverage':'Coffee','Digital Services':'Digital Experiences','Beauty':'Home & Living','Fashion':'Fashion',
              'Outdoor':'Outdoor','Electronics':'Electronics','Education':'Education','Home & Living':'Home & Living'}


def import_legacy(db, path=None):
    source=Path(path or ROOT/'data/commerce_radar.db')
    if not source.exists() or db.get(MigrationState,'legacy-v1'):
        return 0
    count=0
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as old:
        old.row_factory=sqlite3.Row
        tables={r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'transactions','products','users'}.issubset(tables):return 0
        for user in old.execute("SELECT id,display_name FROM users WHERE role='consumer'"):
            if not db.get(User,user['id']):
                db.add(User(id=user['id'],display_name=user['display_name'],persona='Imported consumer'))
                db.flush()
                db.add(InterestProfile(user_id=user['id'],budget_jpy=15000))
        db.flush()
        # The new synthetic persona stories replace old synthetic demo history.
        # Preserve real app Sandbox/simulation purchases, not irrelevant old random histories.
        for row in old.execute("SELECT t.*,p.name AS product_name,p.category AS product_category FROM transactions t JOIN products p ON p.id=t.product_id WHERE t.data_source != 'synthetic' AND t.payment_status='COMPLETED'"):
            if db.scalar(select(Purchase.id).where(Purchase.legacy_id==f'v1:{row["id"]}')):continue
            from datetime import date
            db.add(Purchase(user_id=row['consumer_id'],product_name=row['product_name'] or 'Unknown',
                category=CATEGORY_MAP.get(row['product_category'],'Unknown'),merchant_name='Legacy demo merchant',country_code='JP',
                quantity=row['quantity'],amount=row['amount'],currency=row['currency'],purchased_at=date.fromisoformat(row['transaction_date']),
                source=row['data_source'],paypal_order_id=row['paypal_order_id'],paypal_capture_id=row['paypal_capture_id'],legacy_id=f'v1:{row["id"]}'))
            count+=1
    db.add(MigrationState(key='legacy-v1',value=f'{count} completed app purchases imported; synthetic history retained in original database'))
    db.commit()
    return count
