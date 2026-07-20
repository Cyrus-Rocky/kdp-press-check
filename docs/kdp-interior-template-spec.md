# KDP-Ready Interior Template — Product Spec

This is the blueprint for your **first digital product**: a Word (`.docx`)
manuscript template that is already formatted to KDP's paperback rules, so an
author just pastes their text and exports a clean PDF. It's the file you sell
on the Templates page (`products_data.py` → "KDP-Ready Interior Templates").

You can build this yourself in Microsoft Word in an afternoon, or hand this
whole page to a formatter on Fiverr (~$15–30) and get the files back.

Deliver **one .docx per trim size** (start with 6×9, the most common), bundled
in a zip with a short "how to use" PDF.

---

## 1. Page setup (per trim size)

| Setting | Value (6×9) |
|---|---|
| Page size | 6" wide × 9" tall (Layout → Size → More Paper Sizes) |
| Orientation | Portrait |
| Mirror margins | ON (Layout → Margins → Custom → Multiple pages: "Mirror margins") |
| Inside (gutter) margin | **0.75"** (safe for up to ~150 pages; see note) |
| Outside margin | 0.5" |
| Top margin | 0.75" |
| Bottom margin | 0.75" |

> **Gutter note:** KDP's required inside margin grows with page count
> (0.375" up to 150pp → 0.875" at 700+pp). Ship the template at **0.75" inside**
> (comfortably safe for most first books) and include a one-line note telling
> buyers to widen it for long books — point them at the site's **Margin Advisor**.

Make additional versions for 5×8 and 8.5×11 later using the same rules.

## 2. Fonts

- Body: a clean serif — **Garamond**, **Georgia**, or **Book Antiqua**, 11–12pt.
- Headings: same family or a simple complementary one.
- Use only fonts that embed cleanly. On export, embed all fonts (see §6).
- Line spacing: **1.15–1.5**. First-line indent 0.2"–0.3" on body paragraphs
  (no indent on the first paragraph of a chapter).

## 3. Paragraph / character styles (the important part)

Set these as real Word **Styles** (Home → Styles) so buyers can restyle globally:

- **Title** — for the title page.
- **Chapter Heading** — based on Heading 1. Critically: set **"Page break
  before"** ON (Paragraph → Line and Page Breaks). This makes every chapter
  start on a fresh page automatically (the site's Chapter Page Breaks check
  looks for exactly this).
- **Body Text** — justified, first-line indent, widow/orphan control ON.
- **Body First** — same but no indent (for the first paragraph after a heading).
- **Scene Break** — centered, for a single consistent marker (e.g. `* * *`).

## 4. Front matter (include these pages, pre-built)

In this order, each on its own page:

1. **Title page** — Book Title + Author (Title style, few words).
2. **Copyright page** — placeholder text the buyer edits:
   `Copyright © [Year] [Author Name]. All rights reserved.` plus a spot for
   the ISBN and a "work of fiction" disclaimer line.
3. **Table of Contents** — an auto TOC (References → Table of Contents) that
   updates from the Chapter Heading style.
4. **Chapter 1** starts here.

Then a few sample chapters using the styles, with `[replace with your text]`
placeholders, so the buyer sees how it works.

## 5. Page numbering

- Insert page numbers in the footer, centered or outer.
- Start numbering at the first chapter (front matter unnumbered or roman).
- No page number on chapter-opening pages if you can manage it (nice-to-have).

## 6. Export instructions (put these in the "how to use" PDF)

1. Replace placeholder text with your manuscript.
2. Update the Table of Contents (right-click → Update Field).
3. File → Save As → **PDF** → Options → tick **"ISO 19005-1 compliant (PDF/A)"**
   (this embeds fonts).
4. Run the PDF through **KDP Press Check → Interior Check** before uploading.

---

## Turning it into money (the Gumroad flow)

1. Build the `.docx` (above) + the "how to use" PDF. Zip them.
2. Create a free account at **gumroad.com**.
3. New product → upload the zip → set price **$9** → write the description
   (reuse the bullet points from §1–4) → publish.
4. Copy the product's share link.
5. Paste it into `products_data.py` → the 6×9 template's `buy_url`.
6. The Templates page "Coming soon" becomes a live **"Get it for $9"** button.

Every sale after that is automatic: Gumroad charges the card, emails the buyer
the zip, and pays you. That's the passive part.

**Next products once this sells:** 5×8 and 8.5×11 template versions, a
full-wrap cover template, and a short "Publish your first book on KDP" guide.
