"""Static curated directory of freelancers who specialise in KDP publishing.

Each solver has:
  - name, initials, color  (avatar — no image upload needed for V1)
  - specialty               (display title)
  - categories              (list — used for filter tabs)
  - bio                     (one-sentence pitch)
  - turnaround              (e.g. "3–5 days")
  - platforms               (list of {name, url, icon} — links to their profiles)
  - tags                    (skill chips)

V1: manually curated. V2: self-serve sign-up with a database.
"""

CATEGORIES = [
    {"key": "all",        "label": "All"},
    {"key": "formatting", "label": "Interior Formatting"},
    {"key": "cover",      "label": "Cover Design"},
    {"key": "editing",    "label": "Editing & Proofreading"},
    {"key": "kindle",     "label": "Kindle / EPUB"},
]

SOLVERS = [
    {
        "name": "Marcus J.",
        "initials": "MJ",
        "color": "#A8580F",
        "specialty": "KDP Interior Formatter",
        "categories": ["formatting"],
        "bio": "Specialises in KDP paperback interior layout — trim sizes, margins, bleed-ready PDFs, and front matter. 500+ books formatted since 2016.",
        "turnaround": "2–4 days",
        "tags": ["Trim & Margins", "Bleed Setup", "Front Matter", "Word → PDF"],
        "platforms": [
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=kdp+interior+formatting&source=main_banner", "icon": "F"},
            {"name": "Upwork",  "url": "https://www.upwork.com/search/profiles/?q=kdp+book+formatting",                      "icon": "U"},
        ],
    },
    {
        "name": "Priya S.",
        "initials": "PS",
        "color": "#7B3FA0",
        "specialty": "Book Cover Designer",
        "categories": ["cover"],
        "bio": "Full-wrap KDP cover design with spine-width calculation included. Every file delivered print-ready and KDP-compliant on the first pass.",
        "turnaround": "3–5 days",
        "tags": ["Full Wrap Cover", "Spine Calc", "300 DPI", "CMYK/RGB"],
        "platforms": [
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=kdp+book+cover+design", "icon": "F"},
            {"name": "Kwork",   "url": "https://kwork.com/search?query=book+cover+design+kdp",           "icon": "K"},
        ],
    },
    {
        "name": "Lena T.",
        "initials": "LT",
        "color": "#2E7D32",
        "specialty": "Proofreader & Copy Editor",
        "categories": ["editing"],
        "bio": "Line editing and proofreading for fiction and nonfiction. Catches the typos, repeated words, and inconsistent headings that spell-check misses.",
        "turnaround": "5–7 days",
        "tags": ["Typos", "Repeated Words", "Consistency", "Style Guide"],
        "platforms": [
            {"name": "Upwork",  "url": "https://www.upwork.com/search/profiles/?q=proofreading+book+editor", "icon": "U"},
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=book+proofreading",         "icon": "F"},
        ],
    },
    {
        "name": "Dev R.",
        "initials": "DR",
        "color": "#1565C0",
        "specialty": "Kindle & EPUB Formatter",
        "categories": ["kindle"],
        "bio": "EPUB3 formatting for Kindle Direct Publishing — clean reflow, working TOC, cover embedding, and file-size optimisation to minimise delivery fees.",
        "turnaround": "2–3 days",
        "tags": ["EPUB3", "Kindle Create", "TOC / Nav", "File Size"],
        "platforms": [
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=epub+kindle+formatting", "icon": "F"},
            {"name": "Upwork",  "url": "https://www.upwork.com/search/profiles/?q=epub+kindle+ebook",     "icon": "U"},
        ],
    },
    {
        "name": "Amara O.",
        "initials": "AO",
        "color": "#B71C1C",
        "specialty": "Interior Formatter & Typesetter",
        "categories": ["formatting"],
        "bio": "Professional typesetting for novels, memoirs, and nonfiction using InDesign. Delivers press-ready PDF with embedded fonts and consistent chapter styles.",
        "turnaround": "4–6 days",
        "tags": ["InDesign", "Font Embedding", "Chapter Styles", "Image DPI"],
        "platforms": [
            {"name": "Upwork",  "url": "https://www.upwork.com/search/profiles/?q=book+typesetting+indesign", "icon": "U"},
            {"name": "Kwork",   "url": "https://kwork.com/search?query=typesetting+book",                      "icon": "K"},
        ],
    },
    {
        "name": "Sofia M.",
        "initials": "SM",
        "color": "#00695C",
        "specialty": "Cover Designer & Brand Illustrator",
        "categories": ["cover"],
        "bio": "Genre-savvy cover design for romance, thriller, fantasy, and nonfiction. Includes eBook cover + full-wrap print version in every package.",
        "turnaround": "5–7 days",
        "tags": ["eBook Cover", "Print Wrap", "Genre Design", "Unlimited Revisions"],
        "platforms": [
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=book+cover+design+print", "icon": "F"},
            {"name": "Kwork",   "url": "https://kwork.com/search?query=book+cover+design",                  "icon": "K"},
        ],
    },
    {
        "name": "James A.",
        "initials": "JA",
        "color": "#4A148C",
        "specialty": "Developmental & Structural Editor",
        "categories": ["editing"],
        "bio": "Big-picture editing for plot, structure, pacing, and voice. Works with authors from first draft to final manuscript ready for formatting.",
        "turnaround": "7–14 days",
        "tags": ["Developmental Edit", "Plot & Structure", "Chapter Flow", "Manuscript"],
        "platforms": [
            {"name": "Upwork",  "url": "https://www.upwork.com/search/profiles/?q=developmental+editor+book", "icon": "U"},
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=developmental+editing+book", "icon": "F"},
        ],
    },
    {
        "name": "Nina K.",
        "initials": "NK",
        "color": "#E65100",
        "specialty": "All-in-One KDP Publishing Assistant",
        "categories": ["formatting", "kindle", "cover"],
        "bio": "End-to-end KDP setup: interior formatting, EPUB conversion, cover design, and metadata optimisation — one person, one deadline.",
        "turnaround": "7–10 days",
        "tags": ["Interior + EPUB", "Cover", "Metadata", "KDP Upload"],
        "platforms": [
            {"name": "Fiverr",  "url": "https://www.fiverr.com/search/gigs?query=kdp+publishing+full+service", "icon": "F"},
            {"name": "Upwork",  "url": "https://www.upwork.com/search/profiles/?q=kdp+self+publishing",        "icon": "U"},
        ],
    },
]

# Maps check titles from checker.py/result.html to solver categories
CHECK_TO_CATEGORY = {
    "Trim Size":              "formatting",
    "Margins":                "formatting",
    "Bleed":                  "formatting",
    "Page Size Consistency":  "formatting",
    "Font Embedding":         "formatting",
    "Image Resolution":       "formatting",
    "Cover Dimensions":       "cover",
    "Spine Width":            "cover",
    "Cover Bleed":            "cover",
    "Spelling / Typos":       "editing",
    "Repeated Words":         "editing",
    "Quote Consistency":      "editing",
    "Heading Consistency":    "editing",
    "Navigation / TOC":       "kindle",
    "Cover Image":            "kindle",
    "File Size":              "kindle",
    "Font Licensing":         "kindle",
    "EPUB Structure":         "kindle",
}
