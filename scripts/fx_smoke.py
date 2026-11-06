"""Explicit online read-only FX provider check. Never calls PayPal or OpenAI."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.db import init_db,Session
from backend.seed import seed
from backend.fx import bundle

if __name__=='__main__':
    init_db()
    with Session() as db:
        seed(db)
        data=bundle(db,mode='live')
        print('Effective FX mode:',data['effective_mode'])
        for code,rate in data['rates'].items():
            print(code,rate.get('rate_date','no date'),rate['source'],'stale='+str(rate['stale']))
        if data['warning']:print(data['warning'])
        sys.exit(0 if data['effective_mode'] in ('live','cached') else 1)
