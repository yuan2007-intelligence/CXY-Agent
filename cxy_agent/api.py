"""只读本地开发 API。生产环境应通过 HTTPS 网关提供 data/catalog.json。"""
import json
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from .catalog import collect, plan

_jobs = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2)

def run_job(job_id, interests):
    try:
        result = collect(interests=interests, persist=False)
        update = {"status": "completed", "result": result}
    except Exception:
        import logging
        logging.exception("Interest search failed")
        update = {"status": "failed", "error": "检索失败，请检查服务器网络、模型配置后重试"}
    with _lock:
        _jobs[job_id].update(update)

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .catalog import CATALOG

class Handler(BaseHTTPRequestHandler):
    def respond(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/tasks':
            return self.respond({'error': 'Not found'}, 404)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 16384:
                raise ValueError()
            interests = json.loads(self.rfile.read(size)).get('interests')
            _, groups = plan()
            allowed = {t.split('：', 1)[-1] for words in groups.values() for word in words for t in word.terms}
            if not isinstance(interests, list) or not 1 <= len(interests) <= 100 or any(not isinstance(t, str) or t not in allowed for t in interests):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            return self.respond({'error': '请选择有效关键词'}, 400)
        with _lock:
            now = time.time()
            for key in list(_jobs):
                if _jobs[key]['status'] != 'running' and now - _jobs[key]['created'] > 3600:
                    del _jobs[key]
            if sum(j['status'] == 'running' for j in _jobs.values()) >= 2:
                return self.respond({'error': '服务忙，请稍后重试'}, 429)
            job_id = uuid.uuid4().hex
            _jobs[job_id] = {'status': 'running', 'created': now}
        _pool.submit(run_job, job_id, interests)
        self.respond({'id': job_id, 'status': 'running'}, 202)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith('/api/tasks/'):
            with _lock:
                job = dict(_jobs.get(path.rsplit('/', 1)[-1], {}))
            return self.respond(job or {'error': '任务不存在或已过期，请重新开始'}, 200 if job else 404)
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
