"""Digital products sold to KDP authors (templates, guides).

These are your own products. Set up a store (Gumroad, Lemon Squeezy, Payhip,
etc.), upload the files there, then paste each product's checkout link into
`buy_url`. A product with an empty `buy_url` renders as "Coming soon" so you
can publish the page before every product is ready.

Nothing is charged on this site: the Buy button sends the customer to your
store, which handles payment and delivery.
"""

PRODUCTS = [
    {
        "name": "KDP-Ready Interior Templates",
        "price": "$9",
        "blurb": "Pre-formatted Word (.docx) manuscript templates that already pass the interior check: correct trim size, gutter margins, styles, and front matter.",
        "includes": [
            "5×8, 5.5×8.5, and 6×9 trim sizes",
            "Correct gutter margins built in",
            "Title, copyright, and chapter styles ready to use",
            "Just paste your text and export",
        ],
        "badge": "Most popular",
        "buy_url": "",
    },
    {
        "name": "Full-Wrap Cover Template Pack",
        "price": "$19",
        "blurb": "Print-ready cover templates with the spine, bleed, and barcode zone already mapped, so your cover passes on the first upload.",
        "includes": [
            "Editable PSD and Canva-ready files",
            "Spine-width guides for common page counts",
            "0.125\" bleed and safe zones marked",
            "Barcode keep-clear area drawn in",
        ],
        "badge": "",
        "buy_url": "",
    },
    {
        "name": "First Book on KDP — Publishing Guide",
        "price": "$12",
        "blurb": "A plain-English ebook that walks a first-time author from finished manuscript to live listing, avoiding the rejections this site checks for.",
        "includes": [
            "Step-by-step upload walkthrough",
            "Metadata, keywords, and category strategy",
            "Pricing and royalty basics",
            "A pre-publish checklist you can print",
        ],
        "badge": "",
        "buy_url": "",
    },
]
