"""FastMCP server exposing calculator tools."""

from __future__ import annotations

import os
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

from src.tools import Calculator, DOCXGenerator, PDFGenerator, WebFetcher, WebSearcher

mcp = FastMCP("Calculator Server")
_calculator = Calculator()
_web_fetcher = WebFetcher()
_web_searcher = WebSearcher(api_key=os.getenv("SERPER_API_KEY"))
_pdf_generator = PDFGenerator()
_docx_generator = DOCXGenerator()


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
