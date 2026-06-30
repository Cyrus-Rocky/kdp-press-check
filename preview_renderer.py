"""Renders PDF pages to individual JPEG files for the in-browser book previewer.

Pages are saved to a job directory on disk and served on-demand by the Flask
app — the browser fetches only the two pages currently visible, so total page
count is no longer limited by HTML payload size.

Job dirs live under UPLOAD_DIR/preview_<job_id>/ and are deleted automatically
after PREVIEW_DIR_TTL seconds (30 minutes) on the next preview request.
"""
import json
import os
import shutil
import time

import fitz  # PyMuPDF

RENDER_DPI = 96
JPEG_QUALITY = 78
PREVIEW_DIR_TTL = 1800  # 30 minutes


# ── Directory helpers ─────────────────────────────────────────────────────────

def _job_dir(upload_dir: str, job_id: str) -> str:
    return os.path.join(upload_dir, f"preview_{job_id}")


def cleanup_old_previews(upload_dir: str) -> None:
    cutoff = time.time() - PREVIEW_DIR_TTL
    try:
        for name in os.listdir(upload_dir):
            if not name.startswith("preview_"):
                continue
            path = os.path.join(upload_dir, name)
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_to_dir(pdf_path: str, out_dir: str, kind: str = "interior") -> dict:
    """Render every page of a PDF into JPEG files inside out_dir/<kind>/.

    Returns a metadata dict: {page_count, width_px, height_px, width_in, height_in}.
    """
    dest = os.path.join(out_dir, kind)
    os.makedirs(dest, exist_ok=True)

    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    first_w = first_h = 0

    for i in range(doc.page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        if i == 0:
            first_w, first_h = pix.width, pix.height
        jpeg_bytes = pix.tobytes("jpeg", jpg_quality=JPEG_QUALITY)
        with open(os.path.join(dest, f"{i:04d}.jpg"), "wb") as f:
            f.write(jpeg_bytes)

    # Physical dimensions from the first page
    dims = {"width_in": 0.0, "height_in": 0.0}
    if doc.page_count > 0:
        r = doc[0].rect
        dims = {"width_in": round(r.width / 72, 2), "height_in": round(r.height / 72, 2)}

    page_count = doc.page_count
    doc.close()

    meta = {
        "page_count": page_count,
        "width_px": first_w,
        "height_px": first_h,
        **dims,
    }
    return meta


def render_job(upload_dir: str, job_id: str,
               interior_path: str, cover_path: str = None) -> dict:
    """Render interior (and optional cover) into a job dir. Returns metadata."""
    cleanup_old_previews(upload_dir)

    job = _job_dir(upload_dir, job_id)
    os.makedirs(job, exist_ok=True)

    interior_meta = render_to_dir(interior_path, job, "interior")
    cover_meta = None
    if cover_path:
        cover_meta = render_to_dir(cover_path, job, "cover")

    meta = {"interior": interior_meta, "cover": cover_meta}
    with open(os.path.join(job, "meta.json"), "w") as f:
        json.dump(meta, f)

    return meta


# ── Serving ───────────────────────────────────────────────────────────────────

def page_file(upload_dir: str, job_id: str, kind: str, page_num: int):
    """Return the absolute path to a rendered page file, or None if missing."""
    path = os.path.join(_job_dir(upload_dir, job_id), kind, f"{page_num:04d}.jpg")
    return path if os.path.exists(path) else None


def load_meta(upload_dir: str, job_id: str) -> dict:
    """Load metadata for an existing job. Returns None if the job is gone."""
    meta_path = os.path.join(_job_dir(upload_dir, job_id), "meta.json")
    if not os.path.exists(meta_path):
        return None
    with open(meta_path) as f:
        return json.load(f)
