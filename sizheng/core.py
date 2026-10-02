import collections
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text())

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

class Graph:
    """Entity-linking and real adjacency traversal; JSON is the portable source of truth."""
    def __init__(self, path=None):
        self.data = read_json(path or ROOT / "data/graph.json")
        self.nodes = {n["id"]: n for n in self.data["nodes"]}
        self.facts = {f["id"]: f for f in self.data["facts"]}
        self.adj = collections.defaultdict(list)
        for f in self.facts.values():
            for node in (f["subject"], f["object"]):
                self.adj[node].append(f)
        self.fingerprint = digest(self.data)

    def link(self, text):
        return [n["id"] for n in self.nodes.values()
                if any(alias in text for alias in n.get("aliases", []) if alias)]

    def retrieve(self, text, as_of=None, hops=2, limit=12):
        as_of = as_of or dt.date.today().isoformat()
        frontier = self.link(text)
        seen = set(frontier)
        selected = {}
        for _ in range(hops):
            nxt = []
            for node in frontier:
                for f in self.adj[node]:
                    if f.get("valid_from") and f["valid_from"] > as_of:
                        continue
                    if f.get("valid_to") and f["valid_to"] < as_of:
                        continue
                    selected[f["id"]] = f
                    for other in (f["subject"], f["object"]):
                        if other not in seen:
                            seen.add(other)
                            nxt.append(other)
            frontier = nxt
        # Prefer lexical overlap within the graph-connected evidence candidates.
        bigrams = {text[i:i+2] for i in range(len(text)-1)}
        ranked = sorted(selected.values(), key=lambda f: (-sum(x in f["quote"] for x in bigrams), f["id"]))
        return ranked[:limit]

    def export_sqlite(self, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as c:
            c.executescript("DROP TABLE IF EXISTS nodes; DROP TABLE IF EXISTS facts; CREATE TABLE nodes(id TEXT PRIMARY KEY, body TEXT); CREATE TABLE facts(id TEXT PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT, body TEXT); CREATE INDEX subject_idx ON facts(subject); CREATE INDEX object_idx ON facts(object);")
            c.executemany("INSERT INTO nodes VALUES(?,?)", [(k, canonical(v)) for k,v in self.nodes.items()])
            c.executemany("INSERT INTO facts VALUES(?,?,?,?,?)", [(k,v["subject"],v["predicate"],v["object"],canonical(v)) for k,v in self.facts.items()])

def parse_jev(body):
    if not isinstance(body, dict) or not str(body.get("model", "")).startswith("typesafe/jev-1.13"):
        raise ValueError("Unexpected Jev response model")
    answer = body.get("answers", {}).get("route", {})
    if answer.get("type") != "choice" or answer.get("choice") not in {"routine", "deep", "human"}:
        raise ValueError("Invalid Jev answer")
    probs = answer.get("probabilities")
    import math
    if not isinstance(probs, dict) or set(probs) != {"routine", "deep", "human"}:
        raise ValueError("Invalid Jev probability keys")
    if not all(type(v) in (int,float) and math.isfinite(v) and 0 <= v <= 1 for v in probs.values()):
        raise ValueError("Invalid Jev probabilities")
    if abs(sum(probs.values()) - 1) > .001:
        raise ValueError("Jev probabilities do not sum to one")
    return {"choice": answer["choice"], "probabilities": probs}

def validate_review(review, text, evidence):
    """Check schema, exact spans and citation provenance, not semantic entailment."""
    if not isinstance(review, dict) or review.get("verdict") not in {"no_issue", "issue", "insufficient"}:
        raise ValueError("Invalid verdict")
    if not isinstance(review.get("findings"), list) or not isinstance(review.get("summary"), str):
        raise ValueError("Invalid findings/summary")
    by_id = {f["id"]: f for f in evidence}
    validations = []
    for f in review["findings"]:
        if not isinstance(f, dict): raise ValueError("Invalid finding")
        if not all(isinstance(f.get(k),str) for k in ["span", "type", "explanation", "suggestion"]):
            raise ValueError("Invalid finding fields")
        refs = f.get("evidence_ids")
        quotes = f.get("evidence_quotes")
        if not isinstance(refs,list) or not isinstance(quotes,list) or len(refs) != len(quotes):
            raise ValueError("Invalid citations")
        ok = bool(f["span"]) and f["span"] in text and bool(refs)
        ok = ok and all(isinstance(i,str) and isinstance(q,str) and i in by_id and bool(q) and q in by_id[i]["quote"] for i,q in zip(refs,quotes))
        validations.append(ok)
    if review["verdict"] == "issue" and not review["findings"]:
        raise ValueError("Issue verdict requires findings")
    review["citation_checks"] = validations
    review["citation_status"] = "verified" if validations and all(validations) else "no_findings" if not validations else "invalid"
    review["semantic_entailment_verified"] = False
    return review

def segment(text, maximum=1400):
    if not text.strip() or len(text) > 8000:
        raise ValueError("Text must contain 1–8000 characters; split longer documents explicitly")
    chunks = []
    for paragraph in re.split(r"\n\s*\n", text):
        # Preserve every character; expose neighbouring text to the reviewer separately.
        chunks.extend(paragraph[i:i+maximum] for i in range(0,len(paragraph),maximum) if paragraph[i:i+maximum].strip())
    return chunks
