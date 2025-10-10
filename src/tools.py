"""Calculator and web utility tools for the MCP server."""

from __future__ import annotations

import math
from typing import Union
from urllib.parse import urlparse

import httpx


Number = Union[int, float]


class Calculator:
    """Calculator with basic and advanced mathematical operations."""

    @staticmethod
    def add(a: Number, b: Number) -> float:
        """Add two numbers.

        Args:
            a: The first addend.
            b: The second addend.

        Returns:
            The sum of ``a`` and ``b``.
        """
        return float(a + b)

    @staticmethod
    def subtract(a: Number, b: Number) -> float:
        """Subtract one number from another.

        Args:
            a: The value to subtract from.
            b: The value to subtract.

        Returns:
            The result of ``a - b``.
        """
        return float(a - b)

    @staticmethod
    def multiply(a: Number, b: Number) -> float:
        """Multiply two numbers.

        Args:
            a: The first factor.
            b: The second factor.

        Returns:
            The product of ``a`` and ``b``.
        """
        return float(a * b)

    @staticmethod
    def divide(a: Number, b: Number) -> float:
        """Divide one number by another.

        Args:
            a: The dividend.
            b: The divisor.

        Returns:
            The quotient of ``a / b``.

        Raises:
            ValueError: If ``b`` is zero.
        """
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return float(a / b)

    @staticmethod
    def power(base: Number, exponent: Number) -> float:
        """Raise a base to a power.

        Args:
            base: The base value.
            exponent: The exponent value.

        Returns:
            ``base`` raised to ``exponent``.
        """
        return float(math.pow(base, exponent))

    @staticmethod
    def sqrt(value: Number) -> float:
        """Calculate the square root of a non-negative number.

        Args:
            value: The value whose square root should be calculated.

        Returns:
            The square root of ``value``.

        Raises:
            ValueError: If ``value`` is negative.
        """
        if value < 0:
            raise ValueError("Cannot calculate square root of a negative number.")
        return math.sqrt(value)

    @staticmethod
    def factorial(value: int) -> int:
        """Calculate the factorial of a non-negative integer.

        Args:
            value: The integer whose factorial should be calculated.

        Returns:
            The factorial of ``value``.

        Raises:
            ValueError: If ``value`` is negative.
        """
        if value < 0:
            raise ValueError("Factorial is undefined for negative values.")
        return math.factorial(value)

    @staticmethod
    def percentage(value: Number, percent: Number) -> float:
        """Calculate the percentage of a value.

        Args:
            value: The base value.
            percent: The percentage to apply.

        Returns:
            The result of ``percent`` percent of ``value``.
        """
        return float((value * percent) / 100)


class WebFetcher:
    """Utility for retrieving web content over HTTP."""

    @staticmethod
    async def fetch(url: str, timeout: float = 10.0) -> dict[str, str | int]:
        """Fetch textual content from a URL.

        Args:
            url: Fully-qualified HTTP or HTTPS URL to retrieve.
            timeout: Maximum time to wait for the response, in seconds.

        Returns:
            A dictionary containing the final URL, HTTP status code, and response body.

        Raises:
            ValueError: If the URL scheme is unsupported or the request fails.
        """
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URL must use http or https.")

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                f"Request to {url} failed with status code {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ValueError(f"Request to {url} failed: {exc}") from exc

        max_chars = 500
        content = response.text
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]

        note = (
            f"Content truncated to {max_chars} characters for processing."
            if truncated
            else "Content retrieved successfully."
        )

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_snippet": content,
            "note": note,
        }
