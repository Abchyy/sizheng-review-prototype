import csv
import json
import math
import time
import statistics
from pathlib import Path
from .core import ROOT, write_json, read_json, digest
from .harness import Harness
from .providers import Client, ProviderError

def cases(split):
    return [c for c in map(json.loads,(ROOT/"data/benchmark/cases.jsonl").read_text().splitlines()) if c["split"] == split]

def metrics(rows):
    valid=[r for r in rows if r["execution_status"] == "success"]
    n=len(valid)
    confusion={a:{b:0 for b in ["no_issue","issue","insufficient"]} for a in ["no_issue","issue","insufficient"]}
    for r in valid:confusion[r["expected"]][r["predicted"]]+=1
    tp=confusion["issue"]["issue"];fp=sum(confusion[a]["issue"] for a in ["no_issue","insufficient"])
    fn=sum(confusion["issue"][a] for a in ["no_issue","insufficient"])
    finding_count=sum(r["finding_count"] for r in valid)
    checked=sum(r["verified_finding_count"] for r in valid)
    required=sum(r["required_evidence_count"] for r in valid)
    retrieved=sum(r["retrieved_required_count"] for r in valid)
    all_auto=[r for r in valid if r["auto_clear"]]
    lat=sorted(r["provider_latency_s"] for r in valid)
    return {"n_total":len(rows),"n_valid":n,"failures":len(rows)-n,
        "accuracy":sum(r["expected"]==r["predicted"] for r in valid)/n if n else None,
        "balanced_accuracy":statistics.mean(confusion[a][a]/sum(confusion[a].values()) for a in confusion if sum(confusion[a].values())) if n else None,
        "issue_precision":tp/(tp+fp) if tp+fp else None,"issue_recall":tp/(tp+fn) if tp+fn else None,
        "issue_f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        "missed_issues":fn,"false_issue_flags":fp,
        "auto_clear_coverage":len(all_auto)/len(rows) if rows else None,
        "auto_clear_errors":sum(r["expected"]!="no_issue" for r in all_auto),
        "human_review_fraction":(len(rows)-len(all_auto))/len(rows) if rows else None,
        "llm_call_count":sum(r["llm_calls"] for r in valid),"jev_call_count":sum(r["jev_calls"] for r in valid),
        "citation_literal_validity":checked/finding_count if finding_count else None,
        "retrieval_recall_required_facts":retrieved/required if required else None,
        "provider_latency_p50_s":statistics.median(lat) if lat else None,
        "provider_latency_p95_s":lat[min(len(lat)-1,math.ceil(.95*len(lat))-1)] if lat else None,
        "logical_cost_usd":sum(r["logical_cost_usd"] for r in valid),
        "confusion":confusion}

def row_for(case,mode,result,wall):
    findings=[f for o in result["chunks"] for f in o["review"]["findings"]]
    evidence={f["id"] for o in result["chunks"] for f in o["evidence"]}
    required=set(case["required_evidence_ids"])
    return {"id":case["id"],"group":case["group"],"mode":mode,"execution_status":"success","expected":case["expected_verdict"],"predicted":result["verdict"],
        "auto_clear":result["verdict"]=="no_issue","finding_count":len(findings),
        "verified_finding_count":sum(sum(o["review"]["citation_checks"]) for o in result["chunks"]),
        "required_evidence_count":len(required),"retrieved_required_count":len(required&evidence),
        "llm_calls":sum(t["provider"]=="deepseek" for t in result["traces"]),"jev_calls":sum(t["provider"]=="jev" for t in result["traces"]),
        "provider_latency_s":sum(t["latency_s"] for t in result["traces"]),"wall_s":wall,
        "logical_cost_usd":sum(t.get("cost_usd") or 0 for t in result["traces"]),
        "cache_hits":sum(t.get("cache_hit",False) for t in result["traces"])}

def evaluate(split,modes,limit,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fixture=cases(split);fixture=fixture[:limit] if limit else fixture
    client=Client();h=Harness(client,memory=False)
    rows=[];stop=False
    write_json(out/"run_manifest.json",{"split":split,"modes":modes,"case_ids":[c["id"] for c in fixture],"config":read_json(ROOT/"config.json"),"cases_sha256":digest(fixture),"graph_sha256":h.graph.fingerprint,"implementation_revision":"harness-v1.1","implementation_hashes":{name:digest((ROOT/"sizheng"/name).read_text()) for name in ['core.py','harness.py','providers.py','evaluate.py']},"independent_test":False,"synthetic":True})
    for mode in modes:
        for c in fixture:
            start=time.monotonic()
            # Only text and mode reach the system. Gold labels and case IDs stay here.
            try:
                result=h.review(c["text"],mode)
                write_json(out/f'{mode}/{c["id"]}.json',result)
                row=row_for(c,mode,result,time.monotonic()-start)
            except ProviderError as e:
                row={"id":c["id"],"group":c["group"],"mode":mode,"execution_status":"failed","expected":c["expected_verdict"],"predicted":"insufficient","error":str(e)}
                stop=e.fatal
            rows.append(row)
            print(mode,c["id"],row["execution_status"],row["predicted"],flush=True)
            write_json(out/"rows.json",rows)
            if stop:break
        if stop:break
    summary={mode:metrics([r for r in rows if r["mode"]==mode]) for mode in modes}
    summary["execution"]={"completed":not stop and len(rows)==len(fixture)*len(modes),"actual_paid_requests_in_ledger":client.ledger["requests"],"actual_known_or_estimated_total_cost_usd":client.ledger["known_or_estimated_cost_usd"],"notes":"DeepSeek cost is peak-price estimate, Jev returned cost. Logical per-arm totals include shared cached requests. Provider latency comes from original calls; rerun wall time can be much smaller. No account-bill verification."}
    write_json(out/"summary.json",summary)
    if rows:
        keys=sorted(set().union(*(r.keys() for r in rows)))
        with (out/"predictions.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary
