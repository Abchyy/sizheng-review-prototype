import argparse
import json
from pathlib import Path
from .core import ROOT, Graph, write_json
from .harness import Harness

def main():
    parser=argparse.ArgumentParser(description="Evidence-grounded editorial review")
    subs=parser.add_subparsers(dest="command",required=True)
    r=subs.add_parser("review");r.add_argument("--text");r.add_argument("--file",type=Path)
    r.add_argument("--mode",choices=["hybrid","llm_graph","llm_only","offline"],default="hybrid")
    r.add_argument("--as-of");r.add_argument("--out",type=Path,default=ROOT/"runtime/latest.json")
    subs.add_parser("graph")
    e=subs.add_parser("evaluate");e.add_argument("--split",choices=["dev","test"],default="test")
    e.add_argument("--modes",nargs="+",choices=["hybrid","llm_graph","llm_only"],default=["llm_only","llm_graph","hybrid"])
    e.add_argument("--limit",type=int);e.add_argument("--out",type=Path,default=ROOT/"runtime/evaluation")
    s=subs.add_parser("serve");s.add_argument("--port",type=int,default=8765)
    s.add_argument("--offline",action="store_true")
    subs.add_parser("verify")
    args=parser.parse_args()
    if args.command == "graph":
        graph=Graph();graph.export_sqlite(ROOT/"runtime/graph.sqlite")
        print(json.dumps({"nodes":len(graph.nodes),"facts":len(graph.facts),"sha256":graph.fingerprint}))
    elif args.command == "review":
        if bool(args.text) == bool(args.file):parser.error("Provide exactly one of --text or --file")
        text=args.text if args.text else args.file.read_text()
        result=Harness().review(text,args.mode,args.as_of);write_json(args.out,result)
        print(json.dumps({"verdict":result["verdict"],"requires_human":result["requires_human"],"output":str(args.out)},ensure_ascii=False))
    elif args.command == "evaluate":
        from .evaluate import evaluate
        evaluate(args.split,args.modes,args.limit,args.out)
    elif args.command == "serve":
        from .web import serve
        serve(args.port,args.offline)
    else:
        from .verify import verify
        print(json.dumps(verify(),ensure_ascii=False))

if __name__ == "__main__":main()
