"""Renders PDF pages to base64-encoded JPEG images for the in-browser
book previewer. Uses PyMuPDF (fitz) — already a project dependency.

Keeps rendered images small enough to embed inline in HTML while still
being sharp enough to read text. JPEG at 96 DPI is ~30-80 KB per page
depending on content; 20 pages ≈ 1-1.5 MB total, acceptable for a web page.
"""
import base64
import fitz  # PyMuPDF

RENDER_DPI = 96
JPEG_QUALITY = 78
MAX_PAGES = 20


def render_pages(pdf_path: str, max_pages: int = MAX_PAGES) -> list:
    """Returns a list of dicts: {index, width, height, data_uri}."""
    doc = fitz.open(pdf_path)
    pages = []
    count = min(doc.page_count, max_pages)
    mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    for i in range(count):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        jpeg_bytes = pix.tobytes("jpeg", jpg_quality=JPEG_QUALITY)
        data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()
        pages.append({
            "index": i,
            "width": pix.width,
            "height": pix.height,
            "data_uri": data_uri,
        })
    doc.close()
    return pages


def page_dimensions(pdf_path: str) -> dict:
    """Returns {width_in, height_in, page_count} from the first page."""
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        doc.close()
        return {"width_in": 0, "height_in": 0, "page_count": 0}
    rect = doc[0].rect
    w_in = round(rect.width / 72, 2)
    h_in = round(rect.height / 72, 2)
    count = doc.page_count
    doc.close()
    return {"width_in": w_in, "height_in": h_in, "page_count": count}
