"""FastMCP server exposing calculator tools."""

from __future__ import annotations

from fastmcp import FastMCP

from src.tools import Calculator, WebFetcher

mcp = FastMCP("Calculator Server")
_calculator = Calculator()
_web_fetcher = WebFetcher()


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
