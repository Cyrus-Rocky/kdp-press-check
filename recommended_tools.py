"""Recommended author tools (affiliate).

These are the paid tools your users are most likely to buy next, the ones with
real affiliate programs that pay well because your checks already prove the
need. Sign up for each program, then paste the exact affiliate link it gives
you into `url`. A tool with an empty `url` is hidden, so the box only appears
once you actually earn from it.

Unlike simple query-param affiliates (Amazon's ?tag=), these programs hand you
a whole tracked link, so you paste the full URL here rather than transforming
an existing one.

Where to join:
  - Publisher Rocket: kindlepreneur.com/affiliates (keyword/category research)
  - Atticus: atticus.io affiliate program (writing + formatting)
  - Add your own below the same way.
"""

RECOMMENDED_TOOLS = [
    {
        "name": "Publisher Rocket",
        "blurb": "Go deeper than this linter: find the exact low-competition "
                 "keywords and categories your book can actually rank in.",
        "cta": "See Publisher Rocket",
        "url": "",   # paste your Publisher Rocket affiliate link
    },
    {
        "name": "Atticus",
        "blurb": "Write and format your book in one place and export print + "
                 "ebook files that pass the checks on this site.",
        "cta": "See Atticus",
        "url": "",   # paste your Atticus affiliate link
    },
]


def visible():
    return [t for t in RECOMMENDED_TOOLS if t["url"].strip()]


def enabled() -> bool:
    return len(visible()) > 0
