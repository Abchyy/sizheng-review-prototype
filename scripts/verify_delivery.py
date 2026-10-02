"""Offline integrity and evaluation verification, including sanitized API records."""
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sizheng.core import ROOT, read_json, digest
from sizheng.verify import verify

checksums=read_json(ROOT/'SHA256SUMS.json')
for name,expected in checksums.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
assert verify()['ok']
ledger=read_json(ROOT/'results/api_ledger.json')
cache={p.stem:read_json(p) for p in (ROOT/'results/api_cache').glob('*.json')}
for a in ledger['attempts']:
    if a['status']=='success':
        response=cache[a['cache_id']]
        assert a['response_id']==response['response'].get('id')
        assert response['cache_id']==digest({'url':'https://openrouter.ai/api/alpha/decisions' if a['provider']=='jev' else 'https://api.deepseek.com/chat/completions','payload':response['request']})
total=sum(a.get('cost_usd') or 0 for a in ledger['attempts'])
assert math.isclose(total,ledger['known_or_estimated_cost_usd'],abs_tol=1e-12)
print(json.dumps({'ok':True,'files_verified':len(checksums),'successful_api_records':len(cache),'independent_model_calls':False,'note':'Checks reproduce saved real responses and arithmetic, not provider account billing.'}))
