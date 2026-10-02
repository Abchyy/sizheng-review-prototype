"""Re-fetch only manifest URLs; report changes without modifying frozen evidence."""
import hashlib
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sizheng.core import ROOT, read_json, write_json

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.skip+=1
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

results=[]
for source in read_json(ROOT/'data/sources/manifest.json'):
    row={'id':source['id'],'url':source['url']}
    try:
        raw=urllib.request.urlopen(urllib.request.Request(source['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read()
        parser=Text();parser.feed(raw.decode('utf-8',errors='replace'))
        text=re.sub(r'\s+','', ''.join(parser.parts))
        snippets=(ROOT/source['snapshot_path']).read_text().splitlines()
        row.update(status='downloaded',raw_sha256=hashlib.sha256(raw).hexdigest(),all_excerpts_present=all(re.sub(r'\s+','',q) in text for q in snippets))
    except Exception as e:row.update(status='failed',error_type=type(e).__name__)
    results.append(row);print(json.dumps(row,ensure_ascii=False))
write_json(ROOT/'runtime/source_recheck.json',results)
