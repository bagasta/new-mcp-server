#!/usr/bin/env python3
"""Utility helpers for generating or decoding PDFs used in local testing."""

from __future__ import annotations

import argparse
import sys
from base64 import b64decode
from pathlib import Path

from src.tools import PDFGenerator


def _normalise_base64(data: str) -> str:
    """Strip data-URL prefixes, whitespace, and repair missing padding."""
    cleaned = data.strip()
    if cleaned.startswith("data:"):
        cleaned = cleaned.split(",", 1)[-1]
    cleaned = "".join(cleaned.split())
    padding = len(cleaned) % 4
    if padding:
        cleaned += "=" * (4 - padding)
    return cleaned


def decode_base64_to_pdf(data: str, output: Path) -> Path:
    """Decode a base64 string and write the result to ``output``."""
    pdf_bytes = b64decode(_normalise_base64(data), validate=True)
    output.write_bytes(pdf_bytes)
    return output


def generate_pdf(title: str, content: str, output: Path) -> Path:
    """Use the project PDFGenerator to create a document."""
    generator = PDFGenerator()
    result = generator.generate_pdf(title=title, content=content)
    pdf_bytes = b64decode(result["base64_content"])
    output.write_bytes(pdf_bytes)
    note = result.get("note")
    if note:
        print(note)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a PDF with the MCP PDFGenerator or decode base64 to PDF."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate", help="Generate a PDF using PDFGenerator."
    )
    generate_parser.add_argument("--title", required=True, help="PDF title metadata.")
    generate_parser.add_argument(
        "--content",
        required=True,
        help="Body text for the PDF. Use quotes to preserve spaces/newlines.",
    )
    generate_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("result.pdf"),
        help="Output file path (default: result.pdf).",
    )

    decode_parser = subparsers.add_parser(
        "decode", help="Decode a base64 string and write the PDF to disk."
    )
    decode_parser.add_argument(
        "input",
        help="Path to a file containing base64 data, or '-' to read from stdin.",
    )
    decode_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("result.pdf"),
        help="Output file path (default: result.pdf).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        generate_pdf(args.title, args.content, args.output)
        print(f"Wrote PDF to {args.output.resolve()}")
        return 0

    if args.command == "decode":
        if args.input == "-":
            base64_data = sys.stdin.read()
        else:
            base64_data = Path(args.input).read_text()
        decode_base64_to_pdf(base64_data, args.output)
        print(f"Wrote PDF to {args.output.resolve()}")
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
