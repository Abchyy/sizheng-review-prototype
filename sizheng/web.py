import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from .core import ROOT, Graph
from .harness import Harness
from .providers import ProviderError

def serve(port=8765,offline=False):
    harness=Harness()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,format,*args):pass
        def send(self,data,status=200,kind='application/json; charset=utf-8'):
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.path=='/':return self.send((ROOT/'sizheng/index.html').read_bytes(),kind='text/html; charset=utf-8')
            if self.path=='/api/graph':return self.send(json.dumps(Graph().data,ensure_ascii=False).encode())
            if self.path=='/api/status':return self.send(json.dumps({'offline':offline,'scope':'事实与引用辅助审校','model_version':'请求 V4-Flash，官方实际服务 V4.1-Flash'},ensure_ascii=False).encode())
            return self.send(b'{"error":"not_found"}',404)
        def do_POST(self):
            if self.path!='/api/review':return self.send(b'{"error":"not_found"}',404)
            # Custom header + absent CORS prevents cross-origin browser POSTs to paid API.
            if self.headers.get('X-Review-Request')!='local':return self.send(b'{"error":"invalid_request_origin"}',403)
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{port}',f'http://localhost:{port}'}:return self.send(b'{"error":"invalid_origin"}',403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=40000:raise ValueError('Request too large or empty')
                body=json.loads(self.rfile.read(size));text=body.get('text')
                if not isinstance(text,str):raise ValueError('Text must be a string')
                mode='offline' if offline else body.get('mode','hybrid')
                if mode not in {'offline','hybrid','llm_graph','llm_only'}:raise ValueError('Invalid mode')
                result=harness.review(text,mode)
                # Expose readable evidence and results; provider requests stay server-side.
                result.pop('traces',None)
                return self.send(json.dumps(result,ensure_ascii=False).encode())
            except (ValueError,ProviderError) as e:return self.send(json.dumps({'error':str(e)},ensure_ascii=False).encode(),400)
            except Exception:return self.send(b'{"error":"internal_error"}',500)
    print(f'Local review UI: http://127.0.0.1:{port} (offline={offline})',flush=True)
    HTTPServer(('127.0.0.1',port),Handler).serve_forever()
