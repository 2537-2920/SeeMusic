from __future__ import annotations

import asyncio
import threading
from typing import Any
from urllib.parse import unquote

import httpx


class CompatibilityTestClient:
    """A small sync test client compatible with the current ASGI/httpx stack.

    Starlette's bundled TestClient hangs in the current SeeMusic environment
    (`fastapi 0.135.3`, `starlette 1.0.0`, `httpx 0.28.1`). This shim keeps the
    same test ergonomics while driving the ASGI app through a dedicated asyncio
    loop and direct ASGI calls.

    The current env also exhibits an anyio/asyncio wake-up issue for sync route
    handlers that run in worker threads. A tiny background heartbeat keeps the
    loop responsive while requests and lifespan hooks are in flight.
    """

    __test__ = False

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: str = "asyncio",
        backend_options: dict[str, Any] | None = None,
        cookies: httpx._types.CookieTypes | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
    ) -> None:
        if backend != "asyncio":
            raise NotImplementedError("CompatibilityTestClient only supports the asyncio backend.")

        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.backend_options = backend_options or {}
        self.follow_redirects = follow_redirects
        self.client = client
        self.app_state: dict[str, Any] = {}

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lifespan_cm = None
        self._heartbeat_stop: asyncio.Event | None = None
        self._started = False
        self._request_builder = httpx.Client(
            base_url=self.base_url,
            cookies=cookies,
            headers=headers,
            follow_redirects=follow_redirects,
            trust_env=False,
        )

    def __enter__(self) -> CompatibilityTestClient:
        self._ensure_started()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    async def _heartbeat(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(0.01)

    def _start_loop(self) -> None:
        if self._loop is not None:
            return

        ready = threading.Event()

        def runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._heartbeat_stop = asyncio.Event()
            loop.create_task(self._heartbeat(self._heartbeat_stop))
            ready.set()
            loop.run_forever()

            if self._heartbeat_stop is not None:
                self._heartbeat_stop.set()
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        self._thread = threading.Thread(target=runner, name="compat-test-client", daemon=True)
        self._thread.start()
        ready.wait()

    def _run(self, coroutine):
        if self._loop is None:
            raise RuntimeError("CompatibilityTestClient loop has not been started.")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result()

    async def _async_startup(self) -> None:
        self._lifespan_cm = self.app.router.lifespan_context(self.app)
        lifespan_state = await self._lifespan_cm.__aenter__()
        if isinstance(lifespan_state, dict):
            self.app_state.update(lifespan_state)

    async def _async_shutdown(self) -> None:
        if self._lifespan_cm is not None:
            await self._lifespan_cm.__aexit__(None, None, None)
        self._lifespan_cm = None
        self.app_state.clear()

    def _ensure_started(self) -> None:
        if self._started:
            return
        self._start_loop()
        self._run(self._async_startup())
        self._started = True

    @staticmethod
    def _port_for_scheme(request: httpx.Request) -> int:
        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[request.url.scheme]
        return request.url.port or default_port

    def _build_scope(self, request: httpx.Request) -> dict[str, Any]:
        host = request.url.host or "testserver"
        port = self._port_for_scheme(request)
        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[request.url.scheme]

        if "host" in request.headers:
            headers: list[tuple[bytes, bytes]] = []
        elif port == default_port:
            headers = [(b"host", host.encode())]
        else:
            headers = [(b"host", f"{host}:{port}".encode())]

        headers += [(key.lower().encode(), value.encode()) for key, value in request.headers.multi_items()]

        return {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(request.url.path),
            "raw_path": request.url.raw_path.split(b"?", 1)[0],
            "root_path": self.root_path,
            "scheme": request.url.scheme,
            "query_string": request.url.query,
            "headers": headers,
            "client": self.client,
            "server": [host, port],
            "state": self.app_state.copy(),
            "extensions": {"http.response.debug": {}},
            "app": self.app,
        }

    async def _async_request(self, request: httpx.Request) -> httpx.Response:
        scope = self._build_scope(request)
        request_body = request.read()
        if isinstance(request_body, str):
            request_body = request_body.encode("utf-8")
        elif request_body is None:
            request_body = b""

        request_complete = False
        response_started = False
        response_complete = asyncio.Event()
        response_status = 500
        response_headers: list[tuple[bytes, bytes]] = []
        response_body_chunks: list[bytes] = []
        template = None
        context = None

        async def receive() -> dict[str, Any]:
            nonlocal request_complete

            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            request_complete = True
            return {"type": "http.request", "body": request_body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            nonlocal response_started, response_status, response_headers, template, context

            if message["type"] == "http.response.start":
                if response_started:
                    raise AssertionError('Received multiple "http.response.start" messages.')
                response_status = message["status"]
                response_headers = list(message.get("headers", []))
                response_started = True
                return

            if message["type"] == "http.response.body":
                if not response_started:
                    raise AssertionError('Received "http.response.body" without "http.response.start".')
                if response_complete.is_set():
                    raise AssertionError('Received "http.response.body" after response completed.')

                if request.method != "HEAD":
                    response_body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    response_complete.set()
                return

            if message["type"] == "http.response.debug":
                info = message.get("info", {})
                template = info.get("template")
                context = info.get("context")

        try:
            await self.app(scope, receive, send)
        except BaseException:
            if self.raise_server_exceptions:
                raise
            if not response_started:
                response_status = 500
                response_headers = []
                response_body_chunks = []
                response_complete.set()

        if self.raise_server_exceptions and not response_started:
            raise AssertionError("CompatibilityTestClient did not receive any response.")
        if not self.raise_server_exceptions and not response_started:
            response_status = 500
            response_headers = []
            response_body_chunks = []

        response = httpx.Response(
            status_code=response_status,
            headers=[(key.decode("latin-1"), value.decode("latin-1")) for key, value in response_headers],
            content=b"".join(response_body_chunks),
            request=request,
        )
        if template is not None:
            response.template = template  # type: ignore[attr-defined]
            response.context = context  # type: ignore[attr-defined]
        return response

    def _redirect_request(self, request: httpx.Request, response: httpx.Response) -> httpx.Request | None:
        location = response.headers.get("location")
        if not location:
            return None

        status_code = response.status_code
        method = request.method
        body = request.read()
        headers = request.headers.copy()

        if status_code == 303 and method != "HEAD":
            method = "GET"
            body = b""
            headers.pop("content-length", None)
            headers.pop("content-type", None)
        elif status_code in {301, 302} and method not in {"GET", "HEAD"}:
            method = "GET"
            body = b""
            headers.pop("content-length", None)
            headers.pop("content-type", None)

        redirect_url = request.url.join(location)
        return self._request_builder.build_request(method, redirect_url, content=body, headers=headers)

    def close(self) -> None:
        if self._started:
            self._run(self._async_shutdown())
            self._started = False

        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except RuntimeError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)

        self._loop = None
        self._thread = None
        self._heartbeat_stop = None
        self._request_builder.close()

    def request(self, method: str, url: str, **kwargs):
        self._ensure_started()

        follow_redirects = kwargs.pop("follow_redirects", self.follow_redirects)
        auth = kwargs.pop("auth", None)
        if auth is not None:
            raise NotImplementedError("CompatibilityTestClient does not support auth handlers.")

        request = self._request_builder.build_request(method, url, **kwargs)
        response = self._run(self._async_request(request))
        self._request_builder.cookies.extract_cookies(response)

        redirect_count = 0
        while follow_redirects and response.is_redirect:
            redirect_count += 1
            if redirect_count > 20:
                raise httpx.TooManyRedirects("Exceeded maximum allowed redirects.")

            redirect_request = self._redirect_request(request, response)
            if redirect_request is None:
                break
            request = redirect_request
            response = self._run(self._async_request(request))
            self._request_builder.cookies.extract_cookies(response)

        return response

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def head(self, url: str, **kwargs):
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs):
        return self.request("OPTIONS", url, **kwargs)
