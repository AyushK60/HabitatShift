"""Build the version 3 paper from one Markdown source into LaTeX (for Overleaf) and an HTML preview.

    python scripts/build_paper.py
Reads docs/paper/v3/paper.md and refs.bib. Writes main.tex and paper.html in the same folder. Render the PDF
preview with:  node tools/visual/render_paper_v3.mjs

The Markdown subset: # title, "Key: value" front matter lines, ## / ### headings (numbered by their own text),
paragraphs, **bold**, *italic*, `code`, $math$, $$display$$, [@key] citations, @fig:id and @tab:id references,
`![caption](path){#fig:id width=0.7}` figures and `Table: caption {#tab:id}` followed by a pipe table.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import sys

DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "docs" / "paper" / "v3"
SRC = DIR / "paper.md"
BIB = DIR / "refs.bib"

TEX_SPECIAL = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}


BS = chr(92)
ACCENTS = {BS + "'e": "é", BS + "'E": "É", BS + '"e': "ë", BS + '"o': "ö", BS + "c{c}": "ç"}


def plain(s: str) -> str:
    """Plain text from a BibTeX field for the HTML preview: common accents mapped, protective braces dropped."""
    for k, v in ACCENTS.items():
        s = s.replace("{" + k + "}", v).replace(k, v)
    return s.replace("{", "").replace("}", "")


def parse_bib() -> dict[str, dict]:
    out = {}
    for m in re.finditer(r"@\w+\{(\w+),(.*?)\n\}", BIB.read_text(encoding="utf-8"), re.S):
        fields = dict(re.findall(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*\n", m.group(2) + "\n", re.S))
        out[m.group(1)] = fields
    return out


def split_inline(text: str):
    """Split into ('math', tex) and ('text', str) parts so escaping never touches maths."""
    parts, pos = [], 0
    for m in re.finditer(r"\$\$(.+?)\$\$|\$(.+?)\$", text, re.S):
        if m.start() > pos:
            parts.append(("text", text[pos:m.start()]))
        parts.append(("display" if m.group(1) is not None else "math", m.group(1) if m.group(1) is not None else m.group(2)))
        pos = m.end()
    if pos < len(text):
        parts.append(("text", text[pos:]))
    return parts


class Doc:
    def __init__(self) -> None:
        self.bib = parse_bib()
        self.cite_order: list[str] = []
        self.labels: dict[str, tuple[str, int]] = {}

    def cite_no(self, key: str) -> int:
        if key not in self.cite_order:
            self.cite_order.append(key)
        return self.cite_order.index(key) + 1

    # ---------------------------------------------------------------- LaTeX
    def tex_inline(self, text: str) -> str:
        out = []
        for kind, body in split_inline(text):
            if kind == "math":
                out.append(f"${body}$")
            elif kind == "display":
                out.append(f"\\[{body}\\]")
            else:
                out.append(self.tex_text(body))
        return "".join(out)

    def tex_text(self, t: str) -> str:
        t = re.sub(r"\[@([\w;@ ]+)\]", lambda m: "\x00CITE:" + m.group(1).replace("@", "").replace(" ", "") + "\x00", t)
        t = re.sub(r"@(fig|tab):(\w+)", lambda m: f"\x00REF:{m.group(1)}:{m.group(2)}\x00", t)
        codes: list[str] = []
        t = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00CODE{len(codes) - 1}\x00", t)
        t = re.sub(r"\*\*(.+?)\*\*", "\x00B\x00\\1\x00/B\x00", t)
        t = re.sub(r"\*(.+?)\*", "\x00I\x00\\1\x00/I\x00", t)
        t = "".join(TEX_SPECIAL.get(c, c) if c not in "\x00" else c for c in t)
        t = t.replace("\x00B\x00", r"\textbf{").replace("\x00/B\x00", "}").replace("\x00I\x00", r"\textit{").replace("\x00/I\x00", "}")
        t = re.sub(r"\x00CITE:([\w,;]+)\x00", lambda m: r"\cite{" + m.group(1).replace(";", ",") + "}", t)
        t = re.sub(r"\x00REF:(fig|tab):(\w+)\x00", lambda m: ("Figure~" if m.group(1) == "fig" else "Table~") + r"\ref{" + m.group(1) + ":" + m.group(2) + "}", t)
        t = re.sub(r"\x00CODE(\d+)\x00", lambda m: r"\texttt{" + "".join(TEX_SPECIAL.get(c, c) for c in codes[int(m.group(1))]) + "}", t)
        return t

    # ----------------------------------------------------------------- HTML
    def html_inline(self, text: str) -> str:
        out = []
        for kind, body in split_inline(text):
            if kind in ("math", "display"):
                cls = "math-d" if kind == "display" else "math-i"
                out.append(f'<span class="{cls}" data-tex="{html.escape(body, quote=True)}"></span>')
            else:
                out.append(self.html_text(body))
        return "".join(out)

    def html_text(self, t: str) -> str:
        t = html.escape(t, quote=False)
        t = re.sub(r"\[@([\w;@ ]+)\]", lambda m: "[" + ", ".join(str(self.cite_no(k)) for k in m.group(1).replace("@", "").replace(" ", "").split(";")) + "]", t)
        t = re.sub(r"@(fig|tab):(\w+)", lambda m: ("Figure " if m.group(1) == "fig" else "Table ") + str(self.labels.get(f"{m.group(1)}:{m.group(2)}", ("", "?"))[1]), t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
        return t


def number_labels(doc: Doc, text: str) -> None:
    f = t = 0
    for m in re.finditer(r"\{#(fig|tab):(\w+)", text):
        if m.group(1) == "fig":
            f += 1
            doc.labels[f"fig:{m.group(2)}"] = ("fig", f)
        else:
            t += 1
            doc.labels[f"tab:{m.group(2)}"] = ("tab", t)


def blocks(text: str):
    cur: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if cur:
                yield "\n".join(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        yield "\n".join(cur)


def build() -> None:
    raw = SRC.read_text(encoding="utf-8")
    doc = Doc()
    number_labels(doc, raw)
    title, meta, tex_body, html_body = "", {}, [], []
    sec = sub = 0
    pending_caption: tuple[str, str] | None = None
    in_abstract = False
    for block in blocks(raw):
        if block.startswith("# "):
            title = block[2:].strip()
            continue
        if re.match(r"^(Author|Affiliation|Status):", block):
            for line in block.splitlines():
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
            continue
        if block.startswith("## "):
            name = block[3:].strip()
            if name == "Abstract":
                in_abstract = True
                tex_body.append("\\begin{abstract}")
                html_body.append('<section class="abstract"><h2>Abstract</h2>')
                continue
            if in_abstract:
                in_abstract = False
                tex_body.append("\\end{abstract}")
                html_body.append("</section>")
            if name == "References":
                html_body.append("<h2>References</h2>@@REFS@@")
                tex_body.append("\\bibliographystyle{plainnat}\n\\bibliography{refs}")
                continue
            sec += 1
            sub = 0
            label = re.sub(r"^\d+\s+", "", name)
            tex_body.append(f"\\section{{{doc.tex_inline(label)}}}")
            html_body.append(f"<h2>{sec} {doc.html_inline(label)}</h2>")
            continue
        if block.startswith("### "):
            sub += 1
            label = re.sub(r"^\d+(\.\d+)?\s+", "", block[4:].strip())
            tex_body.append(f"\\subsection{{{doc.tex_inline(label)}}}")
            html_body.append(f"<h3>{sec}.{sub} {doc.html_inline(label)}</h3>")
            continue
        m = re.match(r"^Table: (.+?) \{#tab:(\w+)\}\s*$", block)
        if m:
            pending_caption = (m.group(1), m.group(2))
            continue
        if block.startswith("|"):
            rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in block.splitlines()]
            header, body = rows[0], rows[2:]
            cap, key = pending_caption or ("", "")
            pending_caption = None
            n = doc.labels.get(f"tab:{key}", ("", 0))[1]
            cols = "l" + "r" * (len(header) - 1)
            t = ["\\begin{table}[t]\\centering\\small", f"\\caption{{{doc.tex_inline(cap)}}}\\label{{tab:{key}}}", f"\\begin{{tabular}}{{{cols}}}", "\\toprule",
                 " & ".join(doc.tex_inline(c) for c in header) + " \\\\", "\\midrule"]
            t += [" & ".join(doc.tex_inline(c) for c in r) + " \\\\" for r in body]
            t += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
            tex_body.append("\n".join(t))
            h = [f'<table><caption><b>Table {n}.</b> {doc.html_inline(cap)}</caption><thead><tr>' + "".join(f"<th>{doc.html_inline(c)}</th>" for c in header) + "</tr></thead><tbody>"]
            h += ["<tr>" + "".join(f"<td>{doc.html_inline(c)}</td>" for c in r) + "</tr>" for r in body]
            h.append("</tbody></table>")
            html_body.append("".join(h))
            continue
        m = re.match(r"^!\[(.+?)\]\((.+?)\)\{#fig:(\w+)(?: width=([\d.]+))?\}\s*$", block, re.S)
        if m:
            cap, path, key, width = m.group(1), m.group(2), m.group(3), m.group(4) or "1.0"
            n = doc.labels[f"fig:{key}"][1]
            tex_body.append(f"\\begin{{figure}}[t]\\centering\\includegraphics[width={width}\\linewidth]{{{path}}}\n\\caption{{{doc.tex_inline(cap)}}}\\label{{fig:{key}}}\n\\end{{figure}}")
            html_body.append(f'<figure style="width:{float(width) * 100:.0f}%"><img src="{path}"><figcaption><b>Figure {n}.</b> {doc.html_inline(cap)}</figcaption></figure>')
            continue
        tex_body.append(doc.tex_inline(" ".join(block.splitlines())))
        html_body.append(f"<p>{doc.html_inline(' '.join(block.splitlines()))}</p>")
    if in_abstract:
        tex_body.append("\\end{abstract}")
        html_body.append("</section>")

    preamble = r"""\documentclass[11pt]{article}
\usepackage[a4paper,margin=2.3cm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage[numbers]{natbib}
\usepackage[colorlinks=true,linkcolor=blue!50!black,citecolor=blue!50!black,urlcolor=blue!50!black]{hyperref}
\setlength{\parskip}{0.5em}\setlength{\parindent}{0pt}
\graphicspath{{./}}
"""
    tex = (preamble + f"\\title{{{doc.tex_inline(title)}}}\n\\author{{{meta.get('Author', '')}\\\\ \\small {meta.get('Affiliation', '')}}}\n\\date{{}}\n"
           "\\begin{document}\n\\maketitle\n" + "\n\n".join(tex_body) + "\n\\end{document}\n")
    (DIR / "main.tex").write_text(tex, encoding="utf-8")

    refs = []
    for i, key in enumerate(doc.cite_order, 1):
        f = doc.bib[key]
        authors = plain(f.get("author", "")).replace(" and ", "; ")
        venue = f.get("journal") or f.get("booktitle") or f.get("publisher", "")
        extra = ", ".join(x for x in [f.get("volume"), f.get("pages")] if x)
        refs.append(f"<li>{html.escape(authors)}. {html.escape(f.get('title', '').replace('{', '').replace('}', ''))}. <i>{html.escape(venue.replace('{', '').replace('}', ''))}</i>{', ' + html.escape(extra) if extra else ''} ({f.get('year', '')}).</li>")
    body = "\n".join(html_body).replace("@@REFS@@", "<ol class=\"refs\">" + "".join(refs) + "</ol>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 20mm 18mm; }}
body {{ font: 10.5pt/1.45 "Source Serif 4", Georgia, serif; color: #111; max-width: 170mm; margin: 0 auto; }}
h1 {{ font-size: 18pt; line-height: 1.2; margin: 0 0 6pt; }} .meta {{ font-size: 10pt; color: #333; margin-bottom: 14pt; }}
h2 {{ font-size: 13pt; margin: 16pt 0 4pt; }} h3 {{ font-size: 11pt; margin: 10pt 0 2pt; }} p {{ margin: 0 0 6pt; text-align: justify; hyphens: auto; }}
.abstract {{ border-top: 1px solid #111; border-bottom: 1px solid #111; padding: 4pt 0 2pt; margin-bottom: 8pt; }} .abstract h2 {{ font-size: 11pt; margin-top: 2pt; }} .abstract p {{ font-size: 10pt; }}
figure {{ margin: 8pt auto; break-inside: avoid; }} figure img {{ width: 100%; }} figcaption, caption {{ font-size: 9pt; text-align: left; margin-top: 3pt; }}
table {{ border-collapse: collapse; margin: 8pt auto; font-size: 9pt; break-inside: avoid; }} caption {{ caption-side: top; margin-bottom: 4pt; }}
th, td {{ padding: 2pt 8pt; text-align: right; }} th:first-child, td:first-child {{ text-align: left; }} thead tr {{ border-top: 1.2pt solid #111; border-bottom: 0.6pt solid #111; }} tbody tr:last-child {{ border-bottom: 1.2pt solid #111; }}
code {{ font-size: 9pt; }} ol.refs {{ font-size: 9pt; padding-left: 16pt; }}
</style></head><body>
<h1>{html.escape(title)}</h1><div class="meta">{html.escape(meta.get('Author', ''))}<br>{html.escape(meta.get('Affiliation', ''))}<br><i>{html.escape(meta.get('Status', ''))}</i></div>
{body}
</body></html>"""
    (DIR / "paper.html").write_text(page, encoding="utf-8")
    print(f"wrote main.tex and paper.html; sections {sec}, citations {len(doc.cite_order)}, figures {sum(1 for k in doc.labels if k.startswith('fig'))}, tables {sum(1 for k in doc.labels if k.startswith('tab'))}")


if __name__ == "__main__":
    build()
