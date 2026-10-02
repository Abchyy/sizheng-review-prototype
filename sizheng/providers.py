import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from .core import ROOT, digest, read_json, write_json

class ProviderError(RuntimeError):
    def __init__(self, message, fatal=False):
        super().__init__(message); self.fatal = fatal

class Client:
    def __init__(self, runtime=None, max_requests=100, budget_usd=1.0):
        self.runtime = Path(runtime or ROOT / "runtime")
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.max_requests = max_requests; self.budget = budget_usd
        self.consecutive_failures = 0
        self.ledger_path = self.runtime / "ledger.json"
        self.ledger = read_json(self.ledger_path) if self.ledger_path.exists() else {"requests":0,"known_or_estimated_cost_usd":0,"attempts":[]}

    def post(self, provider, payload):
        url = "https://openrouter.ai/api/alpha/decisions" if provider == "jev" else "https://api.deepseek.com/chat/completions"
        key_name = "OPENROUTER_API_KEY" if provider == "jev" else "DEEPSEEK_API_KEY"
        key = os.environ.get(key_name)
        cache_id = digest({"url":url,"payload":payload})
        cache = self.runtime / "cache" / (cache_id + ".json")
        if cache.exists():
            result = read_json(cache); result["cache_hit"] = True; return result
        if not key: raise ProviderError(f"Missing {key_name}", fatal=True)
        if self.ledger["requests"] >= self.max_requests or self.ledger["known_or_estimated_cost_usd"] >= self.budget:
            raise ProviderError("Request/budget limit reached", fatal=True)
        self.ledger["requests"] += 1
        attempt = {"provider":provider,"cache_id":cache_id,"started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"started"}
        self.ledger["attempts"].append(attempt); write_json(self.ledger_path,self.ledger)
        req = urllib.request.Request(url, data=json.dumps(payload,ensure_ascii=False).encode(), headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req,timeout=75) as r: body=json.load(r)
        except Exception as e:
            self.consecutive_failures += 1
            code = e.code if isinstance(e,urllib.error.HTTPError) else None
            # Never save arbitrary exception/body strings: they can echo secrets or user content.
            attempt.update(status="failed",http_status=code,error_type=type(e).__name__,latency_s=time.monotonic()-start,cost_unknown=True)
            write_json(self.ledger_path,self.ledger)
            raise ProviderError(f"{provider} request failed ({code or type(e).__name__})",fatal=code in (401,402,403,404) or self.consecutive_failures>=3) from None
        self.consecutive_failures=0
        usage=body.get("usage",{})
        if provider == "jev":
            cost=usage.get("cost"); cost_kind="returned" if cost is not None else "unknown"
        else:
            # Peak rates as conservative ceiling; not an account bill.
            hit=usage.get("prompt_cache_hit_tokens",0)
            miss=usage.get("prompt_cache_miss_tokens",max(0,usage.get("prompt_tokens",0)-hit))
            cost=(hit*.006+miss*.30+usage.get("completion_tokens",0)*1.2)/1_000_000
            cost_kind="estimated_peak_ceiling"
        if isinstance(cost,(int,float)): self.ledger["known_or_estimated_cost_usd"] += cost
        attempt.update(status="success",latency_s=time.monotonic()-start,cost_usd=cost,cost_kind=cost_kind,response_id=body.get("id"))
        result={"provider":provider,"request":payload,"response":body,**attempt,"cache_hit":False}
        write_json(cache,result);write_json(self.ledger_path,self.ledger)
        return result
