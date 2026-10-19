"""Code-layer defense: turn a vendor document into the text a person would actually see.

Runs before any model sees the document. Each reader drops content that a browser, PDF viewer, or email
app would not show, strips invisible Unicode, and counts what it removed. It never rewrites visible text,
so a clean quote passes through unchanged.
"""

from __future__ import annotations

import email
import re
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage
from pathlib import Path

from bs4 import BeautifulSoup, Comment
from pypdf import PdfReader

# Zero-width, joiner, bidi-override, and BOM characters: invisible to a reader, used to split keywords.
INVISIBLE_CHARS = re.compile(r"[­᠎​-‏‪-‮⁠-⁤⁪-⁯﻿]")

# Inline CSS that hides an element from a person looking at the page.
HIDDEN_CSS = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*(hidden|collapse)"
    r"|opacity\s*:\s*0*(\.0+)?\s*(;|$|!)"
    r"|font-size\s*:\s*0*(\.\d+)?\s*(px|pt|em|rem|%)?\s*(;|$|!)"
    r"|font-size\s*:\s*[0-2](\.\d+)?\s*px"
    r"|(color)\s*:\s*(#fff\b|#ffffff\b|white\b|rgba?\(\s*255\s*,\s*255\s*,\s*255)"
    r"|(left|top|text-indent|margin-left)\s*:\s*-\d{3,}"
    r"|(height|width|max-height|max-width)\s*:\s*0+(px)?\s*(;|$|!)"
    r"|clip\s*:\s*rect\(\s*0",
    re.I,
)
HIDDEN_TAGS = ["script", "style", "noscript", "template", "iframe", "object", "embed"]

MIN_PDF_FONT_PT = 4.0  # text smaller than this cannot be read on a printed or on-screen page


@dataclass
class CleanDoc:
    text: str
    removed: list[str] = field(default_factory=list)  # short labels of what was dropped, never the content

    def note(self) -> str:
        if not self.removed:
            return ""
        return (f"[Sanitizer: removed {len(self.removed)} hidden item(s) a person would not see: "
                f"{', '.join(sorted(set(self.removed)))}.]\n")


def _strip_invisible(text: str, removed: list[str]) -> str:
    cleaned, n = INVISIBLE_CHARS.subn("", text)
    if n:
        removed.append("invisible unicode characters")
    return cleaned


# ---------------------------------------------------------------- HTML


def _css_hidden_selectors(soup: BeautifulSoup) -> list[str]:
    """Selectors from <style> blocks whose rules hide the element (e.g. `.note { display:none }`)."""
    selectors = []
    for style in soup.find_all("style"):
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", style.get_text()):
            if HIDDEN_CSS.search(body + ";"):
                selectors += [s.strip() for s in sel.split(",") if s.strip() and "@" not in s]
    return selectors


def html_visible_text(html: str) -> CleanDoc:
    removed: list[str] = []
    soup = BeautifulSoup(html, "html.parser")

    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
        removed.append("HTML comment")

    hidden = []
    for sel in _css_hidden_selectors(soup):
        try:
            hidden += [(el, "element hidden by stylesheet") for el in soup.select(sel)]
        except Exception:
            pass
    for el in soup.find_all(True):
        if el.has_attr("hidden") or str(el.get("aria-hidden", "")).lower() == "true":
            hidden.append((el, "hidden attribute"))
        elif el.get("style") and HIDDEN_CSS.search(el["style"] + ";"):
            hidden.append((el, "element hidden by inline style"))
    for el, label in hidden:
        if el.get_text(strip=True) and not el.decomposed:
            removed.append(label)
        if not el.decomposed:
            el.decompose()

    for tag in soup(HIDDEN_TAGS):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    return CleanDoc(_strip_invisible(text, removed), removed)


# ---------------------------------------------------------------- PDF


def pdf_visible_text(path: Path) -> CleanDoc:
    removed: list[str] = []
    parts: list[str] = []
    for page in PdfReader(path).pages:
        box = page.mediabox
        x0, y0, x1, y1 = float(box.left), float(box.bottom), float(box.right), float(box.top)
        state = {"fill": (0.0, 0.0, 0.0), "render": 0}
        stack: list[dict] = []

        def before(op, args, cm, tm):
            if op == b"q":
                stack.append(dict(state))
            elif op == b"Q" and stack:
                state.update(stack.pop())
            elif op == b"rg" and len(args) == 3:
                state["fill"] = tuple(float(a) for a in args)
            elif op == b"g" and len(args) == 1:
                state["fill"] = (float(args[0]),) * 3
            elif op == b"k" and len(args) == 4:
                c, m, y, k = (float(a) for a in args)
                state["fill"] = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
            elif op == b"Tr" and args:
                state["render"] = int(args[0])

        def visit(text, cm, tm, font_dict, font_size):
            if not text.strip():
                parts.append(text)
                return
            # Position and size on the page = text matrix applied to the current transformation matrix.
            a, b, c, d, e, f = cm
            x = tm[4] * a + tm[5] * c + e
            y = tm[4] * b + tm[5] * d + f
            scale = (abs(tm[0] * a + tm[1] * c) ** 2 + abs(tm[0] * b + tm[1] * d) ** 2) ** 0.5
            size = font_size * scale
            if state["render"] == 3:
                removed.append("invisible PDF text (render mode 3)")
            elif size < MIN_PDF_FONT_PT:
                removed.append(f"PDF text under {MIN_PDF_FONT_PT:g}pt")
            elif not (x0 - 1 <= x <= x1 and y0 - 1 <= y <= y1):
                removed.append("PDF text placed off the page")
            elif min(state["fill"]) > 0.95:
                removed.append("white PDF text")
            else:
                parts.append(text)

        page.extract_text(visitor_operand_before=before, visitor_text=visit)
        parts.append("\n")
    text = re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()
    return CleanDoc(_strip_invisible(text, removed), removed)


# ---------------------------------------------------------------- Email


def eml_visible_text(path: Path) -> CleanDoc:
    """The body an email app shows: the HTML part if there is one (sanitized), otherwise plain text.
    Attached HTML or PDF files are sanitized the same way."""
    msg: EmailMessage = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    removed: list[str] = []
    lines = [f"{h}: {msg[h]}" for h in ("From", "To", "Subject", "Date") if msg[h]]

    body = msg.get_body(preferencelist=("html", "plain"))
    if body is not None:
        if body.get_content_type() == "text/html":
            clean = html_visible_text(body.get_content())
            removed += clean.removed
            lines += ["", clean.text]
        else:
            lines += ["", body.get_content().strip()]
        others = [p for p in msg.walk() if p.get_content_type() in ("text/plain", "text/html") and p is not body
                  and not p.get_filename()]
        if others:
            removed.append("alternative email part not shown by the mail app")

    for part in msg.iter_attachments():
        name = part.get_filename() or "attachment"
        ctype = part.get_content_type()
        if ctype == "text/html":
            clean = html_visible_text(part.get_content())
        elif ctype == "application/pdf":
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(part.get_content())
                tmp.flush()
                clean = pdf_visible_text(Path(tmp.name))
        else:
            continue
        removed += clean.removed
        lines += ["", f"[Attachment: {name}]", clean.text]

    return CleanDoc(_strip_invisible("\n".join(lines), removed), removed)


def visible_text(path: Path) -> CleanDoc:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return html_visible_text(path.read_text(encoding="utf-8", errors="replace"))
    if suffix == ".pdf":
        return pdf_visible_text(path)
    if suffix == ".eml":
        return eml_visible_text(path)
    return CleanDoc(f"Unsupported file type: {suffix}")
