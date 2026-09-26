"""OM builder — main orchestrator for Offering Memorandum PDF generation.

Assembles data, renders each page as HTML via Jinja2, converts to PDF
via Playwright, and concatenates into a single document.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import tempfile
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pikepdf
from jinja2 import Environment, FileSystemLoader

from app.om.page_registry import (
    build_page_manifest,
    format_currency,
    format_currency_sf,
    format_number,
    format_pct,
    format_pct_raw,
)
from app.om.renderer import render_pages_to_pdf_sync
from app.om.schemas import OMContext
from app.storage.s3 import get_presigned_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image inlining — convert URLs to base64 data URIs
# ---------------------------------------------------------------------------

_image_cache: dict[str, str] = {}


def _url_to_data_uri(url: str | None) -> str | None:
    """Download an image URL and return a base64 data URI.

    Caches results so the same URL is only downloaded once per OM build.
    Returns None if the download fails.
    """
    if not url:
        return None

    # Return cached result
    if url in _image_cache:
        return _image_cache[url]

    try:
        # Handle file:// paths
        parsed = urlparse(url)
        if parsed.scheme == "file" or not parsed.scheme:
            file_path = Path(parsed.path)
            if file_path.exists():
                data = file_path.read_bytes()
                mime = mimetypes.guess_type(str(file_path))[0] or "image/png"
            else:
                logger.warning("Local file not found: %s", url)
                return None
        else:
            # HTTP(S) URL — download with timeout
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                mime = resp.headers.get("Content-Type", "image/png").split(";")[0].strip()

        b64 = base64.b64encode(data).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"
        _image_cache[url] = data_uri
        return data_uri

    except Exception:
        logger.warning("Failed to download image for base64 encoding: %s", url)
        return None


def _file_to_data_uri(file_path: str | Path) -> str:
    """Convert a local file to a base64 data URI."""
    path = Path(file_path)
    if not path.exists():
        return str(file_path)

    data = path.read_bytes()
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _inline_images_in_context(ctx: OMContext) -> OMContext:
    """Replace all image URLs in the OMContext with base64 data URIs.

    This ensures Playwright can render images without network access.
    """
    data = ctx.model_dump()

    # Hero image
    if data.get("hero_image_url"):
        data["hero_image_url"] = _url_to_data_uri(data["hero_image_url"]) or data["hero_image_url"]

    # Rendering images
    if data.get("rendering_images"):
        for img in data["rendering_images"]:
            if img.get("url"):
                img["url"] = _url_to_data_uri(img["url"]) or img["url"]

    # Lot map
    if data.get("lot_map_url"):
        data["lot_map_url"] = _url_to_data_uri(data["lot_map_url"]) or data["lot_map_url"]

    # Market images
    if data.get("market_images"):
        for img in data["market_images"]:
            if img.get("url"):
                img["url"] = _url_to_data_uri(img["url"]) or img["url"]

    # Sponsor data — logos and project images
    if data.get("sponsor_data"):
        for sponsor in data["sponsor_data"]:
            if sponsor.get("logos"):
                for logo in sponsor["logos"]:
                    if isinstance(logo, dict) and logo.get("url"):
                        logo["url"] = _url_to_data_uri(logo["url"]) or logo["url"]
                    elif isinstance(logo, str):
                        # logos stored as plain URL strings
                        idx = sponsor["logos"].index(logo)
                        sponsor["logos"][idx] = _url_to_data_uri(logo) or logo
            if sponsor.get("projects"):
                for project in sponsor["projects"]:
                    if isinstance(project, dict) and project.get("image_url"):
                        project["image_url"] = _url_to_data_uri(project["image_url"]) or project["image_url"]

    return OMContext(**data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_om(
    ctx: OMContext,
    logo_path: str | None = None,
) -> tuple[bytes, int, list[str]]:
    """Build the complete OM PDF.

    Args:
        ctx: Fully populated OMContext with financial data, narratives,
             images, and comps.
        logo_path: Optional override for the Plumb logo file path.

    Returns:
        Tuple of (pdf_bytes, page_count, html_pages_for_preview).
    """
    # Clear image cache for this build
    _image_cache.clear()

    # 0. Inline all images as base64 data URIs
    ctx = _inline_images_in_context(ctx)

    # 1. Setup Jinja2 environment
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
    )

    # Register custom filters
    env.filters["currency"] = format_currency
    env.filters["currency_sf"] = format_currency_sf
    env.filters["pct"] = format_pct
    env.filters["number"] = format_number
    env.filters["pct_raw"] = format_pct_raw

    # 2. Build page manifest
    manifest = build_page_manifest(ctx)

    # 3. Resolve asset paths — inline CSS for reliable Playwright rendering
    styles_css_path = template_dir / "styles.css"
    styles_css_content = styles_css_path.read_text(encoding="utf-8")
    # Strip the Google Fonts @import — Playwright has no network access from temp files
    # and the import blocks stylesheet parsing. We use system font fallbacks instead.
    styles_css_content = "\n".join(
        line for line in styles_css_content.splitlines()
        if not line.strip().startswith("@import")
    )
    if not logo_path:
        # Try SVG first, then PNG
        svg_path = Path(__file__).parents[2] / "plumb-logo.svg"
        png_path = Path(__file__).parents[2] / "plumb-logo.png"
        if svg_path.exists():
            logo_path = str(svg_path)
        elif png_path.exists():
            logo_path = str(png_path)
        else:
            logo_path = str(svg_path)  # Will fail gracefully
    logo_data_uri = _file_to_data_uri(logo_path)

    # 4. Render each page to HTML, write to temp files
    html_pages: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        html_paths: list[Path] = []

        for i, page_spec in enumerate(manifest):
            page_ctx = page_spec["ctx"]
            page_ctx["logo_path"] = logo_data_uri
            # Cover is page 1 logically but doesn't display a number;
            # numbering starts visible from page 2 onward.
            page_ctx["page_number"] = i + 1

            template = env.get_template(page_spec["template"])
            html = template.render(ctx=page_ctx, styles_css=styles_css_content)
            html_pages.append(html)

            html_path = Path(tmpdir) / f"page_{i:03d}.html"
            html_path.write_text(html, encoding="utf-8")
            html_paths.append(html_path)

        # 5. Batch-render all HTML pages to PDF (single browser instance)
        pdf_page_bytes = render_pages_to_pdf_sync(html_paths)

    # 6. Concatenate into final PDF
    final_pdf = concatenate_pdfs(pdf_page_bytes)

    # Clear cache after build
    _image_cache.clear()

    return final_pdf, len(pdf_page_bytes), html_pages


# ---------------------------------------------------------------------------
# PDF concatenation
# ---------------------------------------------------------------------------


def concatenate_pdfs(pdf_pages: list[bytes]) -> bytes:
    """Concatenate multiple single-page PDFs into one document."""
    output = BytesIO()
    writer = pikepdf.Pdf.new()

    for page_bytes in pdf_pages:
        reader = pikepdf.Pdf.open(BytesIO(page_bytes))
        writer.pages.extend(reader.pages)

    writer.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Context assembly helper
# ---------------------------------------------------------------------------


def _safe_presigned_url(s3_key: str | None) -> str | None:
    """Get a presigned URL, returning None on any failure."""
    if not s3_key:
        return None
    try:
        return get_presigned_url(s3_key)
    except Exception:
        logger.warning("Failed to generate presigned URL for %s", s3_key)
        return None


def build_om_context(
    deal: Any,
    financial_model: dict,
    images: list[Any],
    narratives: dict,
) -> OMContext:
    """Assemble OMContext from deal data, financial model, images, and narratives.

    Args:
        deal: Deal SQLAlchemy model instance.
        financial_model: FinancialModel dict (from app.financial).
        images: List of DealImage model instances.
        narratives: Dict of generated narratives keyed by type.

    Returns:
        Fully populated OMContext ready for build_om().
    """
    mc = deal.market_context or {}

    # ------------------------------------------------------------------
    # Group images by type
    # ------------------------------------------------------------------
    hero = next(
        (img for img in images if img.image_type == "hero_rendering"),
        None,
    )
    renderings = sorted(
        [img for img in images if img.image_type in ("exterior_rendering", "interior_rendering")],
        key=lambda x: x.sort_order,
    )
    lot_map = next(
        (img for img in images if img.image_type == "tax_lot_map"),
        None,
    )
    market_imgs = [img for img in images if img.image_type == "neighborhood_photo"]

    # ------------------------------------------------------------------
    # Property stats from financial model
    # ------------------------------------------------------------------
    fm = financial_model
    inputs = fm.get("inputs", {})
    property_stats = _build_property_stats(deal, fm, inputs)

    # ------------------------------------------------------------------
    # Sponsor data
    # ------------------------------------------------------------------
    sponsor_data: list[dict] = []
    if deal.sponsor:
        sponsors = deal.sponsor if isinstance(deal.sponsor, list) else [deal.sponsor]
        for s in sponsors:
            name = s.get("name", s.get("sponsor_name", ""))
            sponsor_imgs = [
                img for img in images
                if img.image_type == "sponsor_project_photo"
                and img.associated_entity == name
            ]
            sponsor_logos = [
                img for img in images
                if img.image_type == "sponsor_logo"
                and img.associated_entity == name
            ]
            sponsor_data.append({
                "name": name,
                "narrative": narratives.get("sponsor_bios", {}).get(name, []),
                "logos": [
                    {"url": _safe_presigned_url(img.s3_key)}
                    for img in sponsor_logos
                    if _safe_presigned_url(img.s3_key)
                ],
                "projects": [
                    {
                        "image_url": _safe_presigned_url(img.s3_key),
                        "name": img.caption or "",
                        "location": "",
                    }
                    for img in sponsor_imgs
                    if _safe_presigned_url(img.s3_key)
                ],
            })

    # ------------------------------------------------------------------
    # Build the OMContext
    # ------------------------------------------------------------------
    return OMContext(
        deal_id=str(deal.id),
        property_name=deal.property_name or "",
        property_address=deal.property_address or "",
        deal_type_label="CONSTRUCTION FINANCING",
        financial_model=financial_model,
        market_context=mc,
        transaction_overview=narratives.get("transaction_overview"),
        investment_highlights=narratives.get("investment_highlights"),
        market_narrative=narratives.get("market_narrative"),
        sponsor_bios=narratives.get("sponsor_bios"),
        hero_image_url=_safe_presigned_url(hero.s3_key) if hero else None,
        rendering_images=[
            {
                "url": _safe_presigned_url(img.s3_key),
                "caption": img.caption or "",
            }
            for img in renderings
            if _safe_presigned_url(img.s3_key)
        ],
        lot_map_url=_safe_presigned_url(lot_map.s3_key) if lot_map else None,
        market_images=[
            {
                "url": _safe_presigned_url(img.s3_key),
                "caption": img.caption or "",
            }
            for img in market_imgs
            if _safe_presigned_url(img.s3_key)
        ],
        sponsor_data=sponsor_data,
        rent_comps=mc.get("comps", []),
        sales_comps=mc.get("sales_comps", []),
        lease_comps=mc.get("lease_comps", []),
        property_stats=property_stats,
    )


def _build_property_stats(deal: Any, fm: dict, inputs: dict) -> dict:
    """Build formatted property stats dict with human-readable labels."""
    from collections import OrderedDict

    def _fmt_num(val: Any) -> str:
        if val is None:
            return ""
        try:
            num = float(val)
            if num == 0:
                return "0"
            return f"{int(num):,}" if num == int(num) else f"{num:,.0f}"
        except (TypeError, ValueError):
            return str(val)

    stats = OrderedDict()
    stats["Address"] = deal.property_address or ""
    stats["Borough"] = inputs.get("borough", "")
    stats["Block / Lot"] = inputs.get("block_lot", "")
    stats["Zoning"] = inputs.get("zoning_district", inputs.get("zoning", ""))

    # Area metrics
    zfa = fm.get("zfa") or inputs.get("zfa")
    gsf = fm.get("total_gsf") or inputs.get("total_gsf")
    total_units = fm.get("total_units") or inputs.get("total_units")
    res_sf = inputs.get("residential_sf") or inputs.get("nra")
    comm_sf = inputs.get("commercial_sf")

    if zfa:
        stats["ZFA"] = _fmt_num(zfa)
    if gsf:
        stats["GSF"] = _fmt_num(gsf)
    if total_units:
        stats["Residential Units"] = _fmt_num(total_units)
    if res_sf:
        stats["Residential Sq. Ft."] = _fmt_num(res_sf)
    if comm_sf:
        stats["Commercial Sq. Ft."] = _fmt_num(comm_sf)

    # Optional fields — only include if present
    parking = inputs.get("parking_spaces")
    if parking is not None:
        stats["Parking Spaces"] = _fmt_num(parking)
    storage = inputs.get("storage_spaces")
    if storage is not None:
        stats["Storage Spaces"] = _fmt_num(storage)

    # Remove entries with empty values
    return OrderedDict((k, v) for k, v in stats.items() if v not in (None, "", "0"))
