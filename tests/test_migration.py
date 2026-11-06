import sqlite3
from datetime import date
from backend.migration import import_legacy
from backend.models import Purchase
from sqlalchemy import select


def test_legacy_import_read_only_and_idempotent(db,tmp_path):
    legacy=tmp_path/'legacy.db'
    with sqlite3.connect(legacy) as old:
        old.executescript('''CREATE TABLE users(id INTEGER,display_name TEXT,role TEXT);
        CREATE TABLE products(id INTEGER,name TEXT,category TEXT);
        CREATE TABLE transactions(id INTEGER,consumer_id INTEGER,product_id INTEGER,quantity INTEGER,amount INTEGER,currency TEXT,transaction_date TEXT,data_source TEXT,payment_status TEXT,paypal_order_id TEXT,paypal_capture_id TEXT);
        INSERT INTO users VALUES(1,'Legacy Consumer','consumer');
        INSERT INTO products VALUES(1,'Coffee Beans','Food & Beverage');
        INSERT INTO transactions VALUES(1,1,1,1,100,'JPY','2026-11-03','sandbox','COMPLETED','LEGACY-ORDER','LEGACY-CAP');''')
    before=legacy.read_bytes()
    assert import_legacy(db,legacy)==1
    assert import_legacy(db,legacy)==0
    imported=db.scalar(select(Purchase).where(Purchase.paypal_capture_id=='LEGACY-CAP'))
    assert imported.product_name=='Coffee Beans'
    assert imported.offer_id is None
    assert legacy.read_bytes()==before
