"""KDP/Kindle EPUB checks: structural validity, table of contents, cover
image dimensions, oversized images, font-embedding licensing flag, and
delivery file size — the things that get Kindle books rejected or quietly
cost authors money on delivery fees. Parsed by hand (zipfile + XML), the
same approach used for .odt, so no extra dependencies are needed.

EPUB has no fixed printed page, so trim/margin/bleed checks don't apply —
that's covered by the Interior and Cover checkers instead.
"""
import io
import os
import re
import zipfile
from xml.etree import ElementTree as ET

from PIL import Image

import classify
import content_quality
import kdp_rules as rules

_NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
}

FONT_EXTENSIONS = (".ttf", ".otf", ".woff", ".woff2")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _load_opf(zf: zipfile.ZipFile):
    container_xml = zf.read("META-INF/container.xml")
    container_root = ET.fromstring(container_xml)
    rootfile_el = container_root.find(".//container:rootfile", _NS)
    opf_path = rootfile_el.get("full-path")
    opf_root = ET.fromstring(zf.read(opf_path))
    opf_dir = os.path.dirname(opf_path)
    return opf_root, opf_path, opf_dir


def _manifest_items(opf_root):
    """Returns {id: {"href": ..., "media-type": ..., "properties": ...}}"""
    items = {}
    manifest = opf_root.find("opf:manifest", _NS)
    if manifest is None:
        return items
    for item in manifest.findall("opf:item", _NS):
        items[item.get("id")] = {
            "href": item.get("href"),
            "media-type": item.get("media-type", ""),
            "properties": item.get("properties", "") or "",
        }
    return items


def check_structure(zf: zipfile.ZipFile) -> dict:
    names = set(zf.namelist())
    problems = []

    if "mimetype" not in names:
        problems.append("missing the required \"mimetype\" file at the root of the archive")
    else:
        mt = zf.read("mimetype").decode("ascii", errors="replace").strip()
        if mt != "application/epub+zip":
            problems.append(f"the \"mimetype\" file contains \"{mt}\" instead of "
                             f"\"application/epub+zip\"")

    if "META-INF/container.xml" not in names:
        problems.append("missing META-INF/container.xml, which tells readers where to find "
                         "the book's content file")
    else:
        try:
            container_root = ET.fromstring(zf.read("META-INF/container.xml"))
            rootfile_el = container_root.find(".//container:rootfile", _NS)
            if rootfile_el is None or not rootfile_el.get("full-path"):
                problems.append("container.xml doesn't point to a content file")
            elif rootfile_el.get("full-path") not in names:
                problems.append(f"container.xml points to "
                                 f"\"{rootfile_el.get('full-path')}\", which doesn't exist "
                                 f"in the file")
        except ET.ParseError:
            problems.append("container.xml isn't valid XML")

    if not problems:
        try:
            _load_opf(zf)
        except (ET.ParseError, KeyError):
            problems.append("the book's content (.opf) file isn't valid XML")

    ok = len(problems) == 0
    if ok:
        return {"title": "EPUB Structure", "ok": True,
                "summary": "The file is a structurally valid EPUB.",
                "detail": "mimetype, container.xml, and the content file all check out."}
    return {
        "title": "EPUB Structure", "ok": False,
        "summary": "This file is broken at a structural level: " + "; ".join(problems) + ".",
        "fix": "This usually means the EPUB wasn't packaged correctly (zipped wrong, or a "
               "manual edit broke something). Re-export it from whatever tool created it "
               "(Kindle Create, Vellum, Calibre, etc.) rather than trying to fix this by hand.",
        "detail": "; ".join(problems),
    }


def check_navigation(zf: zipfile.ZipFile, opf_root, opf_dir: str, items: dict) -> dict:
    nav_item = next((v for v in items.values() if "nav" in v["properties"].split()), None)
    ncx_item = next((v for v in items.values()
                      if v["media-type"] == "application/x-dtbncx+xml"), None)

    if nav_item is None and ncx_item is None:
        return {
            "title": "Table of Contents", "ok": False,
            "summary": "No table of contents (EPUB3 nav or EPUB2 NCX) was found.",
            "fix": "Add a table of contents in whatever tool created this EPUB — Kindle "
                   "readers rely on it for chapter navigation, and Amazon rejects books "
                   "without one.",
            "detail": "No manifest item has nav properties or the NCX media type.",
        }

    entries = 0
    source = "EPUB3 nav" if nav_item else "EPUB2 NCX"
    try:
        if nav_item:
            path = os.path.normpath(os.path.join(opf_dir, nav_item["href"]))
            root = ET.fromstring(zf.read(path.replace(os.sep, "/")))
            entries = len(root.findall(".//xhtml:nav//xhtml:a", _NS))
        else:
            path = os.path.normpath(os.path.join(opf_dir, ncx_item["href"]))
            root = ET.fromstring(zf.read(path.replace(os.sep, "/")))
            entries = len(root.findall(".//ncx:navPoint", _NS))
    except (KeyError, ET.ParseError):
        return {
            "title": "Table of Contents", "ok": False,
            "summary": f"Found a {source} file, but it couldn't be read.",
            "fix": "The table of contents file is referenced but missing or corrupted — "
                   "re-export the EPUB.",
            "detail": f"Expected to read the {source} document but it failed to parse.",
        }

    if entries == 0:
        return {
            "title": "Table of Contents", "ok": False,
            "summary": f"Found a {source} file, but it has no entries.",
            "fix": "Add chapter entries to your table of contents — an empty TOC isn't "
                   "useful to readers and Kindle Create/KDP may reject it.",
            "detail": f"{source} parsed but contained 0 navigation entries.",
        }

    return {
        "title": "Table of Contents", "ok": True,
        "summary": f"Found a {source} table of contents with {entries} entries.",
        "detail": f"Source: {source}. Entries: {entries}.",
    }


def _find_cover_image_path(opf_root, opf_dir: str, items: dict):
    for item in items.values():
        if "cover-image" in item["properties"].split():
            return os.path.normpath(os.path.join(opf_dir, item["href"])).replace(os.sep, "/")
    metadata = opf_root.find("opf:metadata", _NS)
    if metadata is not None:
        for meta in metadata.findall("opf:meta", _NS):
            if meta.get("name") == "cover":
                cover_id = meta.get("content")
                item = items.get(cover_id)
                if item:
                    return os.path.normpath(os.path.join(opf_dir, item["href"])).replace(os.sep, "/")
    return None


def check_cover_image(zf: zipfile.ZipFile, opf_root, opf_dir: str, items: dict) -> dict:
    cover_path = _find_cover_image_path(opf_root, opf_dir, items)
    if cover_path is None:
        return {
            "title": "Cover Image", "ok": False,
            "summary": "No cover image is declared in this EPUB.",
            "fix": "Mark one image as the cover in your EPUB tool (Kindle Create does this "
                   "automatically; in a manually built EPUB, add properties=\"cover-image\" "
                   "to the cover's manifest item). KDP requires a declared cover.",
            "detail": "No manifest item has cover-image properties, and no <meta name=\"cover\"> "
                      "metadata was found.",
        }

    try:
        with zf.open(cover_path) as f:
            img = Image.open(io.BytesIO(f.read()))
            w, h = img.size
    except (KeyError, OSError):
        return {
            "title": "Cover Image", "ok": False,
            "summary": f"The declared cover image (\"{cover_path}\") couldn't be opened.",
            "fix": "The cover file is referenced but missing or corrupted inside the EPUB — "
                   "re-export it.",
            "detail": f"Failed to open {cover_path} as an image.",
        }

    long_side = max(w, h)
    aspect = h / w if w else 0
    problems = []
    if long_side < rules.KINDLE_COVER_MIN_LONG_SIDE_PX:
        problems.append(f"its longest side is {long_side}px, below Amazon's recommended "
                         f"minimum of {rules.KINDLE_COVER_MIN_LONG_SIDE_PX}px")
    if not (rules.KINDLE_COVER_MIN_ASPECT_RATIO <= aspect <= rules.KINDLE_COVER_MAX_ASPECT_RATIO):
        problems.append(f"its aspect ratio ({w}x{h}, {aspect:.2f}:1 height:width) is outside "
                         f"Kindle's recommended {rules.KINDLE_COVER_MIN_ASPECT_RATIO}:1–"
                         f"{rules.KINDLE_COVER_MAX_ASPECT_RATIO}:1 range")

    if not problems:
        return {
            "title": "Cover Image", "ok": True,
            "summary": f"Cover image is {w}x{h}px — meets Kindle's size and shape guidelines.",
            "detail": f"File: {cover_path}. Dimensions: {w}x{h}px.",
        }
    return {
        "title": "Cover Image", "ok": False,
        "summary": f"Cover image ({w}x{h}px) has issues: " + "; ".join(problems) + ".",
        "fix": f"Re-export your cover at roughly "
               f"{rules.KINDLE_COVER_RECOMMENDED_LONG_SIDE_PX}px on the long side, with a "
               f"height:width ratio close to 1.6:1 (Amazon's classic example is 2560x1600).",
        "detail": f"File: {cover_path}. Dimensions: {w}x{h}px. Aspect ratio: {aspect:.2f}:1.",
    }


def check_image_sizes(zf: zipfile.ZipFile, opf_dir: str, items: dict) -> dict:
    oversized = []
    checked = 0
    for item in items.values():
        href = item["href"]
        if not href.lower().endswith(IMAGE_EXTENSIONS):
            continue
        path = os.path.normpath(os.path.join(opf_dir, href)).replace(os.sep, "/")
        try:
            with zf.open(path) as f:
                img = Image.open(io.BytesIO(f.read()))
                w, h = img.size
        except (KeyError, OSError):
            continue
        checked += 1
        if max(w, h) > rules.KINDLE_IMAGE_MAX_REASONABLE_PX:
            oversized.append(f"{href}: {w}x{h}px")

    if checked == 0:
        return {"title": "Image Sizes", "ok": True,
                "summary": "No images found to check.", "detail": "No image files in manifest."}
    if not oversized:
        return {
            "title": "Image Sizes", "ok": True,
            "summary": f"All {checked} image(s) are reasonably sized for an e-reader screen.",
            "detail": f"Checked {checked} image(s); none exceed "
                      f"{rules.KINDLE_IMAGE_MAX_REASONABLE_PX}px on the long side.",
        }
    return {
        "title": "Image Sizes", "ok": True, "warning_only": True,
        "summary": f"{len(oversized)} of {checked} image(s) are larger than an e-reader "
                   f"screen needs.",
        "fix": f"Resize images over {rules.KINDLE_IMAGE_MAX_REASONABLE_PX}px on the long "
               f"side — e-ink and tablet screens don't show the extra detail, and large "
               f"images just bloat the file (which can cost you more in delivery fees).",
        "detail": "\n".join(oversized[:10]),
    }


def check_font_licensing(items: dict) -> dict:
    font_files = [v["href"] for v in items.values()
                  if v["href"].lower().endswith(FONT_EXTENSIONS)]
    if not font_files:
        return {"title": "Embedded Fonts", "ok": True,
                "summary": "No custom fonts are embedded.",
                "detail": "No font files found in the manifest."}
    return {
        "title": "Embedded Fonts", "ok": True, "warning_only": True,
        "summary": f"{len(font_files)} font file(s) are embedded in this EPUB.",
        "fix": "We can't check font licenses automatically — make sure each embedded font's "
               "license allows redistribution/embedding in a sold ebook. Many free fonts "
               "don't, even if they're free to use in a design.",
        "detail": "\n".join(font_files),
    }


def check_file_size(file_size_bytes: int) -> dict:
    mb = file_size_bytes / (1024 * 1024)
    if mb > rules.KINDLE_MAX_FILE_SIZE_MB:
        return {
            "title": "File Size", "ok": False,
            "summary": f"This file is {mb:.1f} MB, over Amazon's {rules.KINDLE_MAX_FILE_SIZE_MB:.0f} MB limit.",
            "fix": "Compress images inside the EPUB or remove unnecessary embedded assets — "
                   "files over the limit are rejected outright.",
            "detail": f"File size: {mb:.2f} MB.",
        }
    if mb > rules.KINDLE_DELIVERY_FEE_THRESHOLD_MB:
        return {
            "title": "File Size", "ok": True, "warning_only": True,
            "summary": f"This file is {mb:.1f} MB. On KDP's 70% royalty plan, delivery fees "
                       f"are charged per MB over {rules.KINDLE_DELIVERY_FEE_THRESHOLD_MB:.0f} MB.",
            "fix": "Not a rejection risk, but it quietly reduces your royalty per sale. If "
                   "this size comes from images, consider compressing them — Kindle screens "
                   "don't need print-resolution images anyway (see Image Sizes above).",
            "detail": f"File size: {mb:.2f} MB. Delivery fee threshold: "
                      f"{rules.KINDLE_DELIVERY_FEE_THRESHOLD_MB:.0f} MB.",
        }
    return {"title": "File Size", "ok": True,
            "summary": f"This file is {mb:.1f} MB — well under any size concern.",
            "detail": f"File size: {mb:.2f} MB."}


def _spine_text_and_headings(zf: zipfile.ZipFile, opf_root, opf_dir: str, items: dict):
    spine = opf_root.find("opf:spine", _NS)
    text_parts = []
    headings = []
    if spine is None:
        return "", []
    for itemref in spine.findall("opf:itemref", _NS):
        item = items.get(itemref.get("idref"))
        if not item:
            continue
        path = os.path.normpath(os.path.join(opf_dir, item["href"])).replace(os.sep, "/")
        try:
            root = ET.fromstring(zf.read(path))
        except (KeyError, ET.ParseError):
            continue
        for el in root.iter():
            tag = _local(el.tag)
            if tag in ("h1", "h2", "h3"):
                text = "".join(el.itertext()).strip()
                if text:
                    headings.append(text)
        text_parts.append(" ".join(t.strip() for t in root.itertext() if t.strip()))
    return "\n".join(text_parts), headings


def run_all_checks_epub(path: str) -> dict:
    file_size = os.path.getsize(path)
    with zipfile.ZipFile(path) as zf:
        structure_result = check_structure(zf)
        results = [structure_result]

        if structure_result["ok"]:
            opf_root, opf_path, opf_dir = _load_opf(zf)
            items = _manifest_items(opf_root)

            full_text, headings = _spine_text_and_headings(zf, opf_root, opf_dir, items)
            word_count = len(full_text.split())
            estimated_pages = max(1, round(word_count / 280)) if word_count else 1
            classification = classify.classify(estimated_pages, full_text, 0.0, 0.0)
            doc_type_result = {"title": "Document Type", "ok": classification["kind"] == "book",
                                "summary": classification["summary"]}
            if classification.get("fix"):
                doc_type_result["fix"] = classification["fix"]
            doc_type_result["detail"] = f"~{estimated_pages} page(s) estimated from word " \
                                         f"count. Classified as: {classification['kind']}."
            results.append(doc_type_result)

            results.append(check_navigation(zf, opf_root, opf_dir, items))
            results.append(check_cover_image(zf, opf_root, opf_dir, items))
            results.append(check_image_sizes(zf, opf_dir, items))
            results.append(check_font_licensing(items))
            results.append(check_file_size(file_size))
            results += content_quality.run(full_text, headings)
        else:
            estimated_pages = 1

    blocking_results = [r for r in results if not r.get("warning_only")]
    summary_ok = all(r["ok"] for r in blocking_results)
    issue_count = sum(1 for r in blocking_results if not r["ok"])

    return {
        "page_count": estimated_pages,
        "page_count_is_estimate": True,
        "results": results,
        "overall_ok": summary_ok,
        "issue_count": issue_count,
    }
