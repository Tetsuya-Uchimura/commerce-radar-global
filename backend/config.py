"""Server-only configuration; existing .env values are never overwritten."""
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{(ROOT / "data/global_radar.db").as_posix()}')
APP_URL = os.getenv('APP_URL', 'http://localhost:5173').rstrip('/')
DEMO_MODE = os.getenv('DEMO_MODE', 'true').lower() == 'true'
DEMO_DATE = date.fromisoformat(os.getenv('DEMO_DATE') or date.today().isoformat())
