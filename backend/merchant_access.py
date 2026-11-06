"""User-maintained merchant policy; affiliate hosts are never merchant identity."""
from pathlib import Path
from urllib.parse import urlparse
import json,re

POLICY_PATH=Path(__file__).with_name('merchant_access.json')

def manual_mode():
    return json.loads(POLICY_PATH.read_text(encoding='utf-8')).get('review_mode')=='manual'

def domain(value):
    try:
        host=(urlparse(value if '://' in value else 'https://'+value).hostname or '').lower().rstrip('.')
        if host.startswith('www.'):host=host[4:]
        return host if re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',host) else None
    except (ValueError,TypeError):return None

def decision(merchant):
    host=domain(str(merchant or ''))
    policy=json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    for action in ('exclude','allow'):
        for configured in policy[action]:
            candidate=domain(configured)
            if candidate and host and (host==candidate or host.endswith('.'+candidate)):
                return {'decision':action,'merchant_domain':host,'matched_domain':candidate,
                    'source':policy['source'],'reviewed_on':policy['reviewed_on'],'scope':policy['scope']}
    return None
