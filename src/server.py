"""FastMCP server exposing calculator and reminder tools."""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

try:  # Lazy dependency: load .env if python-dotenv is available
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore[assignment]


def _load_env() -> None:
    """Load environment variables from a .env file if available."""
    if load_dotenv is not None:
        load_dotenv()
        return

    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()

from src.reminders import (
    ReminderDispatcher,
    ReminderRepository,
    ReminderService,
    MessageSender,
    DeepResearchSender,
)
from src.tools import Calculator, DOCXGenerator, PDFGenerator, WebFetcher, WebSearcher

LOGGER = logging.getLogger("mcp.server")


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:  # pragma: no cover - configuration guard
        LOGGER.warning("Invalid %s value '%s'. Using default %s.", name, value, default)
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:  # pragma: no cover - configuration guard
        LOGGER.warning("Invalid %s value '%s'. Using default %s.", name, value, default)
        return default


def _env_path(name: str, default: str) -> Path:
    value = os.getenv(name)
    return Path(value) if value else Path(default)

mcp = FastMCP("Calculator Server")
_calculator = Calculator()
_web_fetcher = WebFetcher()
_web_searcher = WebSearcher(api_key=os.getenv("SERPER_API_KEY"))
_pdf_generator = PDFGenerator()
_docx_generator = DOCXGenerator()
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    _reminder_repository = ReminderRepository(database_url=DATABASE_URL)
else:
    _reminder_repository = ReminderRepository(
        sqlite_path=_env_path("REMINDER_DB_PATH", "data/reminders.db")
    )
_reminder_dispatcher = ReminderDispatcher(
    _reminder_repository,
    poll_interval=_env_float("REMINDER_POLL_INTERVAL_SECONDS", 30.0),
    batch_size=_env_int("REMINDER_DISPATCH_BATCH_SIZE", 10),
    http_timeout=_env_float("REMINDER_HTTP_TIMEOUT_SECONDS", 10.0),
    retry_base_seconds=_env_float("REMINDER_RETRY_BASE_SECONDS", 30.0),
    retry_max_seconds=_env_float("REMINDER_RETRY_MAX_SECONDS", 600.0),
)
_reminder_service = ReminderService(
    repository=_reminder_repository,
    dispatcher=_reminder_dispatcher,
    webhook_url=os.getenv(
        "REMINDER_WEBHOOK_URL", "https://example.com/webhooks/reminders"
    ),
    min_lead_seconds=_env_float("REMINDER_MIN_LEAD_SECONDS", 5.0),
)
_message_sender = MessageSender(
    webhook_url=os.getenv("MESSAGE_WEBHOOK_URL")
    or os.getenv("REMINDER_WEBHOOK_URL", "https://example.com/webhooks/messages"),
    http_timeout=_env_float("MESSAGE_HTTP_TIMEOUT_SECONDS", 10.0),
)
_deep_research_sender = DeepResearchSender(
    webhook_url=os.getenv("DEEP_RESEARCH_WEBHOOK_URL")
    or os.getenv("MESSAGE_WEBHOOK_URL")
    or os.getenv("REMINDER_WEBHOOK_URL", "https://example.com/webhooks/deep-research"),
    http_timeout=_env_float("DEEP_RESEARCH_HTTP_TIMEOUT_SECONDS", 10.0),
)


def _wrap_result(value: float | int) -> dict[str, float | int]:
    """Wrap primitive tool results in a structured response."""
    return {"result": value}


@mcp.tool()
async def add(a: float, b: float) -> dict[str, float]:
    """Add two numbers.

    Args:
        a: The first addend.
        b: The second addend.

    Returns:
        A dictionary containing the sum of the provided values.
    """
    return _wrap_result(_calculator.add(a, b))


@mcp.tool()
async def subtract(a: float, b: float) -> dict[str, float]:
    """Subtract one number from another.

    Args:
        a: The value to subtract from.
        b: The value to subtract.

    Returns:
        A dictionary containing the result of ``a - b``.
    """
    return _wrap_result(_calculator.subtract(a, b))


@mcp.tool()
async def multiply(a: float, b: float) -> dict[str, float]:
    """Multiply two numbers.

    Args:
        a: The first factor.
        b: The second factor.

    Returns:
        A dictionary containing the product of ``a`` and ``b``.
    """
    return _wrap_result(_calculator.multiply(a, b))


@mcp.tool()
async def divide(a: float, b: float) -> dict[str, float]:
    """Divide one number by another.

    Args:
        a: The dividend.
        b: The divisor.

    Returns:
        A dictionary containing the quotient of ``a / b``.

    Raises:
        ValueError: If ``b`` is zero.
    """
    return _wrap_result(_calculator.divide(a, b))


@mcp.tool()
async def power(base: float, exponent: float) -> dict[str, float]:
    """Raise a base to a power.

    Args:
        base: The base value.
        exponent: The exponent value.

    Returns:
        A dictionary containing ``base`` raised to the ``exponent`` power.
    """
    return _wrap_result(_calculator.power(base, exponent))


@mcp.tool()
async def sqrt(value: float) -> dict[str, float]:
    """Calculate a square root.

    Args:
        value: The value whose square root should be calculated.

    Returns:
        A dictionary containing the square root of ``value``.

    Raises:
        ValueError: If ``value`` is negative.
    """
    return _wrap_result(_calculator.sqrt(value))


@mcp.tool()
async def factorial(value: int) -> dict[str, int]:
    """Calculate a factorial.

    Args:
        value: The non-negative integer whose factorial should be calculated.

    Returns:
        A dictionary containing the factorial of ``value``.

    Raises:
        ValueError: If ``value`` is negative.
    """
    return _wrap_result(_calculator.factorial(value))


@mcp.tool()
async def percentage(value: float, percent: float) -> dict[str, float]:
    """Calculate a percentage of a number.

    Args:
        value: The base value.
        percent: The percentage to apply.

    Returns:
        A dictionary containing the percentage result.
    """
    return _wrap_result(_calculator.percentage(value, percent))


@mcp.tool()
async def fetch_web_content(url: str, timeout: float = 10.0) -> dict[str, str | int]:
    """Retrieve web content from a URL.

    Args:
        url: HTTP or HTTPS URL to fetch.
        timeout: Maximum time to wait for a response in seconds.

    Returns:
        A dictionary with the resolved URL, status code, and a text snippet.

    Raises:
        ValueError: If the URL scheme is unsupported or the request fails.
    """
    return await _web_fetcher.fetch(url, timeout)


@mcp.tool()
async def schedule_reminder(
    title: str,
    message: str,
    target_time_iso: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Schedule a reminder to be dispatched to the configured webhook.

    Args:
        title: Human readable title for the reminder.
        message: Contextual description of the reminder.
        target_time_iso: ISO-8601 timestamp (with timezone) when the reminder should fire.
        payload: Channel-specific payload forwarded to the webhook (e.g., WhatsApp data).

    Returns:
        Structured information about the scheduled reminder, including its identifier.
    """
    return await _reminder_service.schedule_reminder(
        title=title,
        message=message,
        target_time_iso=target_time_iso,
        payload=payload,
    )


@mcp.tool()
async def list_reminders(status: str | None = None, limit: int = 20) -> dict[str, Any]:
    """List reminders currently tracked by the MCP server."""
    reminders = _reminder_service.list_reminders(status=status, limit=limit)
    return {
        "note": "Reminder listing generated.",
        "status": status or "any",
        "count": len(reminders),
        "reminders": reminders,
    }


@mcp.tool()
async def cancel_reminder(reminder_id: str) -> dict[str, Any]:
    """Cancel a pending reminder using its identifier."""
    result = _reminder_service.cancel_reminder(reminder_id)
    result["note"] = "Reminder cancelled successfully."
    return result


@mcp.tool()
async def send_message(to: str, message: str) -> dict[str, Any]:
    """Send an immediate notification to the configured webhook.

    Args:
        to: Recipient identifier understood by downstream automation.
        message: Text body to forward to the downstream channel.

    Returns:
        Structured confirmation describing the delivered message.
    """
    return await _message_sender.send(to=to, message=message)


@mcp.tool()
async def deep_research(search_topic: str, email: str) -> dict[str, Any]:
    """Trigger an n8n deep-research workflow with the provided inputs.

    Args:
        search_topic: Topic that should be investigated by the downstream workflow.
        email: Recipient email address for the deep research results.

    Returns:
        Structured confirmation describing the triggered workflow request.
    """
    return await _deep_research_sender.trigger(search_topic=search_topic, email=email)


@mcp.tool()
async def web_search(
    query: str,
    country: str = "us",
    language: str = "en",
    num_results: int = 5,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Search the web using the Serper API.

    Args:
        query: Search query string.
        country: Two-letter country code for search localisation.
        language: Two-letter language code for search localisation.
        num_results: Maximum number of results to return (1-10).
        timeout: Timeout for the Serper API request in seconds.

    Returns:
        A dictionary containing structured search results.

    Raises:
        ValueError: If the query is empty or the Serper API request fails.
    """
    return await _web_searcher.search(
        query,
        country=country,
        language=language,
        num_results=num_results,
        timeout=timeout,
    )


@mcp.tool()
def pdf_generate(
    title: str,
    content: str,
    filename: str | None = None,
    author: str | None = None,
) -> dict[str, Any]:
    """Generate a PDF document from text content.

    Args:
        title: Title to embed in the PDF.
        content: Text content to render.
        filename: Optional filename for the generated PDF.
        author: Optional author metadata for the PDF.

    Returns:
        A dictionary containing metadata and base64-encoded PDF content.

    Raises:
        ValueError: If required fields are missing.
    """
    return _pdf_generator.generate_pdf(
        title=title,
        content=content,
        filename=filename,
        author=author,
    )


@mcp.tool()
def docx_generate(
    title: str,
    content: str,
    filename: str | None = None,
    author: str | None = None,
) -> dict[str, Any]:
    """Generate a DOCX document from text content."""
    return _docx_generator.generate_docx(
        title=title,
        content=content,
        filename=filename,
        author=author,
    )
