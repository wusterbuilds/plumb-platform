"""PDF parsing via PyMuPDF — renders pages to PNG images for Claude Vision."""

import base64
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class PageImage:
    page_number: int  # 1-indexed
    image_bytes: bytes

    @property
    def base64(self) -> str:
        return base64.standard_b64encode(self.image_bytes).decode("ascii")

    def to_claude_content(self) -> dict:
        """Format as a Claude Vision image content block."""
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": self.base64,
            },
        }


def pdf_to_page_images(pdf_bytes: bytes, dpi: int = 150) -> list[PageImage]:
    """Render each page of a PDF to a PNG image."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(matrix=matrix)
        pages.append(PageImage(page_number=i + 1, image_bytes=pix.tobytes("png")))
    doc.close()
    return pages


def chunk_pages(
    pages: list[PageImage], max_pages: int = 25, overlap: int = 1
) -> list[list[PageImage]]:
    """Split pages into chunks for large documents.

    Each chunk has at most `max_pages` pages. Adjacent chunks share
    `overlap` pages so context isn't lost at boundaries.
    """
    if len(pages) <= max_pages:
        return [pages]

    chunks = []
    start = 0
    while start < len(pages):
        end = min(start + max_pages, len(pages))
        chunks.append(pages[start:end])
        # Advance by (max_pages - overlap), but at least 1
        step = max(max_pages - overlap, 1)
        start += step
        # If remaining pages would be just the overlap, merge into last chunk
        if start < len(pages) and len(pages) - start <= overlap:
            chunks[-1] = pages[chunks[-1][0].page_number - 1 :]
            break
    return chunks


def get_page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages in a PDF without rendering."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    count = len(doc)
    doc.close()
    return count
