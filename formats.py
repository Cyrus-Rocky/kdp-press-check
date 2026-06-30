"""Plain-text extraction for manuscript formats that don't carry print-ready
page geometry: .txt, .rtf, .odt. These formats can't tell us trim size,
margins, or bleed (there's no fixed page to measure), so we only run
document-type classification and content-quality checks on them, and say so
plainly in the UI rather than pretending to check things we can't see.
"""
import zipfile
from xml.etree import ElementTree as ET

from striprtf.striprtf import rtf_to_text

WORDS_PER_PAGE_ESTIMATE = 280

_ODT_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


def extract_txt(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    return {"full_text": text, "headings": []}


def extract_rtf(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        rtf_source = raw.decode("utf-8")
    except UnicodeDecodeError:
        rtf_source = raw.decode("latin-1", errors="replace")
    text = rtf_to_text(rtf_source, errors="ignore")
    return {"full_text": text, "headings": []}


def extract_odt(path: str) -> dict:
    with zipfile.ZipFile(path) as z:
        content_xml = z.read("content.xml")
    root = ET.fromstring(content_xml)

    paragraphs = []
    headings = []
    body = root.find("office:body", _ODT_NS)
    text_root = body.find("office:text", _ODT_NS) if body is not None else None
    if text_root is not None:
        for el in text_root.iter():
            tag = el.tag.split("}")[-1]
            if tag in ("p", "h"):
                text = "".join(el.itertext())
                if tag == "h":
                    headings.append(text)
                paragraphs.append(text)

    return {"full_text": "\n".join(paragraphs), "headings": headings}


EXTRACTORS = {
    ".txt": extract_txt,
    ".rtf": extract_rtf,
    ".odt": extract_odt,
}


def extract(path: str, ext: str) -> dict:
    fn = EXTRACTORS.get(ext)
    if fn is None:
        raise ValueError(f"No extractor for {ext}")
    data = fn(path)
    word_count = len(data["full_text"].split())
    data["estimated_pages"] = max(1, round(word_count / WORDS_PER_PAGE_ESTIMATE)) if word_count else 1
    return data
