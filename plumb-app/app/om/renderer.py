"""HTML-to-PDF renderer using Playwright.

Renders standalone HTML files to single-page 10"x7.5" landscape PDFs
suitable for OM slide decks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def render_page_to_pdf(
    html_path: str | Path,
    width: str = "10in",
    height: str = "7.5in",
) -> bytes:
    """Render a single HTML file to a single-page PDF.

    Args:
        html_path: Absolute path to the HTML file.
        width: Page width (default: landscape 10in).
        height: Page height (default: landscape 7.5in).

    Returns:
        Raw PDF bytes for the single page.
    """
    html_path = Path(html_path).resolve()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{html_path}", wait_until="networkidle")
        pdf_bytes = await page.pdf(
            width=width,
            height=height,
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            prefer_css_page_size=True,
        )
        await browser.close()
        return pdf_bytes


async def render_pages_to_pdf(
    html_paths: list[Path],
    width: str = "10in",
    height: str = "7.5in",
) -> list[bytes]:
    """Render multiple HTML pages, reusing a single browser instance.

    Args:
        html_paths: List of absolute paths to HTML files.
        width: Page width (default: landscape 10in).
        height: Page height (default: landscape 7.5in).

    Returns:
        List of raw PDF bytes, one per input page, in order.
    """
    results: list[bytes] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for html_path in html_paths:
            resolved = Path(html_path).resolve()
            page = await browser.new_page()
            await page.goto(f"file://{resolved}", wait_until="networkidle")
            pdf_bytes = await page.pdf(
                width=width,
                height=height,
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
            )
            results.append(pdf_bytes)
            await page.close()
        await browser.close()
    return results


def render_page_to_pdf_sync(
    html_path: str | Path,
    width: str = "10in",
    height: str = "7.5in",
) -> bytes:
    """Synchronous wrapper for use in Celery tasks."""
    return asyncio.run(render_page_to_pdf(html_path, width=width, height=height))


def render_pages_to_pdf_sync(
    html_paths: list[Path],
    width: str = "10in",
    height: str = "7.5in",
) -> list[bytes]:
    """Synchronous wrapper for batch rendering in Celery tasks."""
    return asyncio.run(render_pages_to_pdf(html_paths, width=width, height=height))
