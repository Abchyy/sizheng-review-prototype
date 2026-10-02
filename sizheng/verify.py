import hashlib
import json
from .core import ROOT, Graph, digest, read_json

def verify():
    graph=Graph();sources={s["id"]:s for s in read_json(ROOT/"data/sources/manifest.json")}
    for s in sources.values():
        raw=(ROOT/s["snapshot_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s["excerpt_sha256"],s["id"]
    for f in graph.facts.values():
        assert f["subject"] in graph.nodes and f["object"] in graph.nodes
        assert f["quote"] in (ROOT/sources[f["source_id"]]["snapshot_path"]).read_text()
        assert f["source_url"]==sources[f["source_id"]]["url"]
    frozen=read_json(ROOT/"data/benchmark/frozen.json")
    for field,path in [('config_sha256','config.json'),('graph_sha256','data/graph.json'),('cases_sha256','data/benchmark/cases.jsonl')]:
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==frozen[field]
    cases=list(map(json.loads,(ROOT/"data/benchmark/cases.jsonl").read_text().splitlines()))
    assert len({c["text"] for c in cases})==len(cases)
    splits={}
    for c in cases:
        splits.setdefault(c["group"],set()).add(c["split"])
        assert set(c["required_evidence_ids"]) <= set(graph.facts)
    assert all(len(s)==1 for s in splits.values())
    evaluation=ROOT/"results/evaluation"
    if (evaluation/"rows.json").exists() and (evaluation/"summary.json").exists():
        from .evaluate import metrics, row_for
        rows=read_json(evaluation/"rows.json");by_id={c['id']:c for c in cases}
        for r in rows:
            if r['execution_status']=='success':
                result=read_json(evaluation/f'{r["mode"]}/{r["id"]}.json')
                assert row_for(by_id[r['id']],r['mode'],result,r['wall_s'])==r
                for trace in result['traces']:
                    request=trace['request']
                    assert 'expected_verdict' not in json.dumps(request)
                    assert 'required_evidence_ids' not in json.dumps(request)
        summary=read_json(evaluation/'summary.json')
        for mode in ['hybrid','llm_graph','llm_only']:
            if mode in summary: assert metrics([r for r in rows if r['mode']==mode])==summary[mode]
    return {"ok":True,"source_count":len(sources),"nodes":len(graph.nodes),"facts":len(graph.facts),"synthetic_cases":len(cases),"group_splits_disjoint":True,"evaluation_recomputed":(evaluation/"rows.json").exists()}
