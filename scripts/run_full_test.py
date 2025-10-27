#!/usr/bin/env python3
"""End-to-end integration test harness for the MCP Calculator project.

This script exercises the core MCP tools, document generators, reminder
workflow, and HTTP transports without requiring any external services.

It starts a local webhook catcher that receives reminder/message/deep-research
callbacks, configures the environment so `src.server` wires those callbacks to
the catcher, and then drives each tool through the FastMCP dispatcher.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import importlib
import io
import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional
from zipfile import BadZipFile, ZipFile

import httpx
import sys

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


UTC = timezone.utc


# --------------------------------------------------------------------------- #
# Result tracking                                                             #
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class TestRecord:
    name: str
    status: str
    detail: str | None = None


class TestSuite:
    """Lightweight test recorder with summary output."""

    def __init__(self) -> None:
        self._records: list[TestRecord] = []

    def success(self, name: str, detail: str | None = None) -> None:
        self._records.append(TestRecord(name, "PASS", detail))

    def fail(self, name: str, detail: str) -> None:
        self._records.append(TestRecord(name, "FAIL", detail))

    def skip(self, name: str, reason: str) -> None:
        self._records.append(TestRecord(name, "SKIP", reason))

    def expect_true(self, name: str, condition: bool, detail: str | None = None) -> None:
        if condition:
            self.success(name, detail)
        else:
            self.fail(name, detail or "Expected truthy result.")

    def expect_equal(self, name: str, actual: Any, expected: Any) -> None:
        if actual == expected:
            self.success(name, f"== {expected!r}")
        else:
            self.fail(name, f"Expected {expected!r}, got {actual!r}.")

    def expect_almost_equal(
        self,
        name: str,
        actual: float,
        expected: float,
        *,
        tolerance: float = 1e-6,
    ) -> None:
        if abs(actual - expected) <= tolerance:
            self.success(name, f"{actual} ~= {expected}")
        else:
            self.fail(
                name,
                f"Expected {expected} +/- {tolerance}, got {actual}.",
            )

    def expect_contains(self, name: str, needle: str, haystack: str) -> None:
        if needle in haystack:
            self.success(name)
        else:
            self.fail(name, f"Did not find {needle!r} in payload.")

    def report(self) -> None:
        """Print a concise summary."""
        total = len(self._records)
        failures = [record for record in self._records if record.status == "FAIL"]
        skips = [record for record in self._records if record.status == "SKIP"]

        print("\n=== MCP Calculator Integration Test Summary ===")
        print(f"Total: {total}  Passed: {total - len(failures) - len(skips)}  "
              f"Skipped: {len(skips)}  Failed: {len(failures)}")
        for record in self._records:
            suffix = f" - {record.detail}" if record.detail else ""
            print(f"[{record.status}] {record.name}{suffix}")
        if failures:
            print("\nFailures detected.")

    @property
    def exit_code(self) -> int:
        return 0 if all(record.status != "FAIL" for record in self._records) else 1


# --------------------------------------------------------------------------- #
# Local webhook catcher                                                       #
# --------------------------------------------------------------------------- #

class _WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler that records POST payloads and serves simple GET responses."""

    server_version = "MCPWebhookTest/0.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - BaseHTTPRequestHandler API
        return  # Silence the default stderr logging.

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        body = f"Stub response for {self.path}".encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            body_text = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            body_text = raw_body.decode("utf-8", errors="replace")

        request_record = {
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers),
            "body": body_text,
        }
        self.server.request_queue.put(request_record)  # type: ignore[attr-defined]

        response = b'{"ok": true}'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class RecordingWebhookServer:
    """Threaded HTTP server that records incoming POST requests."""

    def __init__(self) -> None:
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._backlog: list[dict[str, Any]] = []
        self.url: str | None = None

    def start(self) -> None:
        if self._server is not None:
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), _WebhookHandler)
        server.request_queue = queue.Queue()  # type: ignore[attr-defined]
        self._server = server
        self.url = f"http://127.0.0.1:{server.server_port}"
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._server = None
        self._thread = None

    async def wait_for(self, path: str, timeout: float = 5.0) -> dict[str, Any]:
        """Wait for a request with the specified path to arrive."""
        if not self._server:
            raise RuntimeError("Webhook server is not running.")

        deadline = time.monotonic() + timeout
        while True:
            # Check queued backlog first (requests fetched earlier but unmatched).
            for index, record in enumerate(self._backlog):
                if record.get("path") == path:
                    return self._backlog.pop(index)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for webhook {path!r}.")
            try:
                record = await asyncio.to_thread(
                    self._server.request_queue.get, True, min(0.5, remaining)  # type: ignore[attr-defined]
                )
            except queue.Empty:
                continue

            if record.get("path") == path:
                return record
            self._backlog.append(record)


# --------------------------------------------------------------------------- #
# Environment management                                                      #
# --------------------------------------------------------------------------- #

@contextlib.contextmanager
def configure_runtime_env(stub_url: str, sqlite_path: Path) -> Iterable[None]:
    """Temporarily set env vars so src.server wires network calls to the stub."""

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    updates = {
        "REMINDER_WEBHOOK_URL": f"{stub_url}/reminders",
        "MESSAGE_WEBHOOK_URL": f"{stub_url}/messages",
        "DEEP_RESEARCH_WEBHOOK_URL": f"{stub_url}/deep-research",
        "REMINDER_DB_PATH": str(sqlite_path),
        "REMINDER_MIN_LEAD_SECONDS": "0.5",
        "REMINDER_POLL_INTERVAL_SECONDS": "0.2",
        "REMINDER_RETRY_BASE_SECONDS": "0.5",
        "REMINDER_RETRY_MAX_SECONDS": "1.0",
        "MESSAGE_HTTP_TIMEOUT_SECONDS": "3.0",
        "DEEP_RESEARCH_HTTP_TIMEOUT_SECONDS": "3.0",
        "REMINDER_HTTP_TIMEOUT_SECONDS": "3.0",
    }

    original = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, prior in original.items():
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior


# --------------------------------------------------------------------------- #
# Test helpers                                                                #
# --------------------------------------------------------------------------- #

async def test_calculator_tools(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
) -> None:
    cases = [
        ("add", {"a": 2, "b": 3}, 5.0),
        ("subtract", {"a": 10, "b": 4}, 6.0),
        ("multiply", {"a": 7, "b": 6}, 42.0),
        ("divide", {"a": 9, "b": 3}, 3.0),
        ("power", {"base": 2, "exponent": 8}, 256.0),
        ("sqrt", {"value": 81}, 9.0),
        ("factorial", {"value": 6}, 720),
        ("percentage", {"value": 200, "percent": 12.5}, 25.0),
    ]

    for tool_name, arguments, expected in cases:
        try:
            result = await call_tool(tool_name, **arguments)
        except Exception as exc:  # noqa: BLE001 - test assertion
            suite.fail(f"{tool_name} tool", f"Raised unexpected error: {exc}")
            continue

        value = result.get("result")
        if isinstance(expected, float):
            suite.expect_almost_equal(f"{tool_name} tool", float(value), expected)
        else:
            suite.expect_equal(f"{tool_name} tool", value, expected)


async def test_calculator_error_handling(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
) -> None:
    try:
        await call_tool("divide", a=1, b=0)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "Cannot divide by zero" in message:
            suite.success("divide by zero guard")
        else:
            suite.fail("divide by zero guard", f"Unexpected exception: {message}")
    else:
        suite.fail("divide by zero guard", "Tool did not raise an error.")


def test_pdf_generation(suite: TestSuite, pdf_generator_cls: Any) -> None:
    generator = pdf_generator_cls()
    result = generator.generate_pdf(title="Integration Test", content="Hello MCP!")
    suite.expect_contains("PDF generator note", "PDF", result.get("note", ""))

    try:
        pdf_bytes = base64.b64decode(result["base64_content"])
    except (KeyError, ValueError) as exc:
        suite.fail("PDF generator output", f"Invalid base64 content: {exc}")
        return
    suite.expect_true("PDF header", pdf_bytes.startswith(b"%PDF-"))


def test_docx_generation(suite: TestSuite, docx_generator_cls: Any) -> None:
    generator = docx_generator_cls()
    result = generator.generate_docx(title="Integration Test", content="Hello DOCX!")
    try:
        docx_bytes = base64.b64decode(result["base64_content"])
    except (KeyError, ValueError) as exc:
        suite.fail("DOCX generator output", f"Invalid base64 content: {exc}")
        return

    try:
        with ZipFile(io.BytesIO(docx_bytes)) as archive:
            suite.expect_true("DOCX contains document.xml", "word/document.xml" in archive.namelist())
    except BadZipFile as exc:
        suite.fail("DOCX file structure", f"Unreadable DOCX archive: {exc}")


async def test_web_fetch(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
    stub_url: str,
) -> None:
    target = f"{stub_url}/web-fetch"
    try:
        result = await call_tool("fetch_web_content", url=target, timeout=5.0)
    except Exception as exc:  # noqa: BLE001
        suite.fail("fetch_web_content tool", f"Raised unexpected error: {exc}")
        return

    suite.expect_equal("fetch_web_content status", result.get("status_code"), 200)
    snippet = result.get("content_snippet", "")
    suite.expect_contains("fetch_web_content snippet", "Stub response", snippet)


async def test_web_search(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
) -> None:
    if not os.getenv("SERPER_API_KEY"):
        suite.skip("web_search tool", "SERPER_API_KEY not configured; skipping API call.")
        return

    try:
        result = await call_tool("web_search", query="Model Context Protocol", num_results=1)
    except Exception as exc:  # noqa: BLE001
        suite.fail("web_search tool", f"Raised unexpected error: {exc}")
        return

    suite.expect_true("web_search results", bool(result.get("results")))


async def test_reminder_pipeline(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
    webhook_server: RecordingWebhookServer,
) -> None:
    fire_at = datetime.now(UTC) + timedelta(seconds=2)
    args = {
        "title": "Reminder One",
        "message": "Wake up MCP!",
        "target_time_iso": fire_at.isoformat().replace("+00:00", "Z"),
        "payload": {"to": "integration", "message": "Ping!"},
    }

    try:
        schedule_result = await call_tool("schedule_reminder", **args)
    except Exception as exc:  # noqa: BLE001
        suite.fail("schedule_reminder tool", f"Raised unexpected error: {exc}")
        return

    reminder_id = schedule_result.get("reminder_id")
    suite.expect_true("schedule_reminder id", bool(reminder_id))

    try:
        webhook = await webhook_server.wait_for("/reminders", timeout=8.0)
    except TimeoutError as exc:
        suite.fail("reminder webhook dispatch", str(exc))
        webhook = None

    if webhook:
        suite.expect_contains("reminder webhook payload", reminder_id or "", webhook.get("body", ""))

    listing = await call_tool("list_reminders", status=None, limit=10)
    suite.expect_true("list_reminders response", listing.get("count", 0) >= 1)

    # Schedule a second reminder further in the future and cancel it.
    fire_later = datetime.now(UTC) + timedelta(seconds=120)
    second = await call_tool(
        "schedule_reminder",
        title="Reminder Two",
        message="Cancel me",
        target_time_iso=fire_later.isoformat().replace("+00:00", "Z"),
        payload={"to": "integration", "message": "Cancel"},
    )
    second_id = second.get("reminder_id")
    suite.expect_true("second reminder id", bool(second_id))

    try:
        cancelled = await call_tool("cancel_reminder", reminder_id=second_id)
    except Exception as exc:  # noqa: BLE001
        suite.fail("cancel_reminder tool", f"Raised unexpected error: {exc}")
    else:
        suite.expect_equal("cancel_reminder status", cancelled.get("status"), "cancelled")


async def test_message_sender(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
    webhook_server: RecordingWebhookServer,
) -> None:
    result = await call_tool("send_message", to="tester", message="Hello from MCP")
    suite.expect_equal("send_message status", result.get("status_code"), 200)

    webhook = await webhook_server.wait_for("/messages", timeout=5.0)
    suite.expect_contains("send_message webhook payload", "Hello from MCP", webhook.get("body", ""))


async def test_deep_research(
    suite: TestSuite,
    call_tool: Callable[..., Awaitable[Dict[str, Any]]],
    webhook_server: RecordingWebhookServer,
) -> None:
    result = await call_tool("deep_research", search_topic="LangChain MCP", email="integration@example.com")
    suite.expect_equal("deep_research status", result.get("status_code"), 200)

    webhook = await webhook_server.wait_for("/deep-research", timeout=5.0)
    suite.expect_contains("deep_research webhook payload", "LangChain MCP", webhook.get("body", ""))


async def test_rest_api_transport(
    suite: TestSuite,
    api_app: Any,
) -> None:
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp-api", timeout=10.0) as client:
        tools_response = await client.get("/tools")
        suite.expect_equal("REST /tools status", tools_response.status_code, 200)
        tools_payload = tools_response.json()
        suite.expect_true("REST /tools payload", bool(tools_payload.get("tools")))

        execute_response = await client.post(
            "/execute",
            json={"tool_name": "add", "arguments": {"a": 5, "b": 7}},
        )
        suite.expect_equal("REST /execute status", execute_response.status_code, 200)
        data = execute_response.json()
        suite.expect_equal("REST /execute result", data.get("result", {}).get("result"), 12.0)


async def test_transport_smoke(
    suite: TestSuite,
    name: str,
    app: Any,
    path: str,
) -> None:
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=f"http://{name}", timeout=5.0) as client:
            response = await client.get(path)
    except Exception as exc:  # noqa: BLE001
        suite.fail(f"{name} transport smoke", f"Request failed: {exc}")
        return
    suite.expect_true(
        f"{name} transport smoke",
        response.status_code < 500,
        f"Unexpected status: {response.status_code}",
    )


# --------------------------------------------------------------------------- #
# Main runner                                                                 #
# --------------------------------------------------------------------------- #

async def run_suite(args: argparse.Namespace) -> TestSuite:
    suite = TestSuite()
    webhook_server = RecordingWebhookServer()
    webhook_server.start()

    with TemporaryDirectory() as tmpdir:
        reminder_db = Path(tmpdir) / "reminders.db"

        with configure_runtime_env(webhook_server.url or "http://127.0.0.1:0", reminder_db):
            # Reload src.server so it picks up our environment overrides.
            server_module = importlib.import_module("src.server")
            server = importlib.reload(server_module)
            from fastmcp.server.context import Context  # Imported after env is ready
            from src.tools import DOCXGenerator, PDFGenerator
            from src.transports import api as transport_api
            from src.transports import sse as transport_sse
            from src.transports import streamable as transport_streamable

            if webhook_server.url is None:
                raise RuntimeError("Webhook server URL is not available.")

            # Ensure webhook-enabled components use the local recorder.
            reminder_webhook = f"{webhook_server.url}/reminders"
            message_webhook = f"{webhook_server.url}/messages"
            deep_research_webhook = f"{webhook_server.url}/deep-research"
            server._reminder_service._webhook_url = reminder_webhook  # type: ignore[attr-defined]
            server._message_sender._webhook_url = message_webhook  # type: ignore[attr-defined]
            server._deep_research_sender._webhook_url = deep_research_webhook  # type: ignore[attr-defined]

            async def call_tool(name: str, **kwargs: Any) -> Dict[str, Any]:
                async with Context(fastmcp=server.mcp):
                    tool_result = await server.mcp._call_tool(name, kwargs)
                if tool_result.structured_content is not None:
                    return tool_result.structured_content
                return {
                    "content": [block.model_dump(mode="json") for block in tool_result.content]
                }

            try:
                await test_calculator_tools(suite, call_tool)
                await test_calculator_error_handling(suite, call_tool)
                test_pdf_generation(suite, PDFGenerator)
                test_docx_generation(suite, DOCXGenerator)
                await test_web_fetch(suite, call_tool, webhook_server.url or "")
                await test_web_search(suite, call_tool)
                await test_reminder_pipeline(suite, call_tool, webhook_server)
                await test_message_sender(suite, call_tool, webhook_server)
                await test_deep_research(suite, call_tool, webhook_server)
                await test_rest_api_transport(suite, transport_api.app)
                await test_transport_smoke(suite, "sse", transport_sse.app, "/openapi.json")
                await test_transport_smoke(suite, "streamable", transport_streamable.app, "/openapi.json")
            finally:
                await server._reminder_dispatcher.shutdown()  # type: ignore[attr-defined]

    webhook_server.stop()
    return suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run integration checks against the MCP Calculator project."
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    suite = asyncio.run(run_suite(args))
    suite.report()
    return suite.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
