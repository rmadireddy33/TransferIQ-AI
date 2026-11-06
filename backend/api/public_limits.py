"""Bounded, process-local public request budgets for the one-worker demo."""
from collections import OrderedDict
import math
import threading
import time
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException


class PublicRequestBudget:
    def __init__(self):
        self.clients = OrderedDict()
        self.window = 0.0
        self.total = 0
        self.lock = threading.Lock()

    def allow(self, client, per_client, global_limit):
        now = time.monotonic()
        with self.lock:
            if now >= self.window + 60:
                self.window, self.total = now, 0
                self.clients.clear()
            count = self.clients.get(client, 0)
            retry = max(1, math.ceil(self.window + 60 - now))
            if count >= per_client or self.total >= global_limit:
                return False, retry
            self.total += 1
            self.clients[client] = count + 1
            self.clients.move_to_end(client)
            if len(self.clients) > 2048:
                self.clients.popitem(last=False)
            return True, retry


class PublicLimits:
    def __init__(self, app):
        self.app = app
        self.budget = PublicRequestBudget()
        self.creation_budget = PublicRequestBudget()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope['path']
        public = path == '/api/demo' or path.startswith('/api/demo/') or path in (
            '/docs', '/docs/oauth2-redirect', '/redoc', '/openapi.json')
        if public:
            settings = scope['app'].state.settings
            # Use ASGI peer identity; never parse caller-supplied forwarding headers.
            client = (scope.get('client') or ('unknown',))[0]
            allowed, retry = self.budget.allow(client, settings.public_demo_requests_per_minute,
                                                settings.public_demo_global_requests_per_minute)
            if allowed and path.rstrip('/') in ('/api/demo/runs', '/api/demo/runs/review') and scope['method'] == 'POST':
                allowed, retry = self.creation_budget.allow(client, 5, 20)
            status, code = (None, None) if allowed else (429, 'rate_limited')
            if len(path) > 512 or len(scope.get('query_string', b'')) > 1024:
                status, code = 414, 'request_too_long'
            headers = dict(scope.get('headers', []))
            is_demo_write = path.startswith('/api/demo/runs') and scope['method'] == 'POST'
            body_limit = 32768 if path.endswith('/resolution-plans/preview') else (8192 if '/resolution-plans/' in path and path.endswith('/decision') else 4096)
            if is_demo_write and (not headers.get(b'content-length', b'0').isdigit() or
                                 int(headers.get(b'content-length', b'0')) > body_limit):
                status, code = 413, 'body_too_large'
            if scope['method'] in ('GET', 'HEAD') and (
                headers.get(b'content-length', b'0') != b'0' or b'transfer-encoding' in headers):
                status, code = 413, 'body_not_allowed'
            if status:
                response = JSONResponse({'detail': {'code': code, 'message': 'Public request limit exceeded'}},
                    status_code=status, headers={'Retry-After': str(retry), 'Cache-Control': 'no-store'})
                return await response(scope, receive, send)
            if is_demo_write:
                original_receive = receive
                received = 0
                async def bounded_receive():
                    nonlocal received
                    message = await original_receive()
                    received += len(message.get('body', b''))
                    if received > body_limit:
                        raise HTTPException(413, detail={'code': 'body_too_large', 'message': 'Demo request exceeds bounded body size'})
                    return message
                receive = bounded_receive
        return await self.app(scope, receive, send)
