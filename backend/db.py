from pathlib import Path
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from .config import DATABASE_URL, ROOT
from .models import Base

(ROOT / 'data').mkdir(exist_ok=True)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 30})


@event.listens_for(engine, 'connect')
def sqlite_settings(connection, _):
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA journal_mode=WAL')


Session = sessionmaker(engine, expire_on_commit=False)


def init_db():
    tables = inspect(engine).get_table_names()
    if 'merchants' in tables:
        raise RuntimeError('DATABASE_URL points to the legacy database. Keep it intact and use a new global_radar.db path.')
    Base.metadata.create_all(engine)
    # Additive migration: preserve every payment's original amount/currency.
    additions = {'product_offers': {'checkout_usd':'INTEGER', 'available_in_us':'BOOLEAN'},
                 'purchase_transactions': {'notes':"TEXT NOT NULL DEFAULT ''", 'deleted':'BOOLEAN NOT NULL DEFAULT 0'},
                 'interest_profiles': {'budget_usd':'INTEGER NOT NULL DEFAULT 15000'}}
    with engine.begin() as connection:
        for table, fields in additions.items():
            existing = {c['name'] for c in inspect(connection).get_columns(table)}
            for name, definition in fields.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {definition}'))


def get_db():
    with Session() as session:
        yield session
