"""只读本地开发 API。生产环境应通过 HTTPS 网关提供 data/catalog.json。"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .catalog import CATALOG

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path not in ('/api/catalog', '/health'):
            self.send_error(404)
            return
        if path == '/health':
            payload = {'ok': True}
        elif CATALOG.exists():
            payload = json.loads(CATALOG.read_text())
        else:
            payload = {'updatedAt': None, 'items': [], 'keywords': {}, 'message': '尚未采集，请先运行采集命令'}
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8787), Handler).serve_forever()
