#!/usr/bin/env python3
"""Convert a Markdown file to PDF via Playwright (Chromium print)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    print("Installing markdown…", file=sys.stderr)
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "markdown"])
    import markdown

from playwright.sync_api import sync_playwright

CSS = """
@page { margin: 18mm 16mm; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #1a1a1a;
  max-width: 100%;
}
h1 { font-size: 20pt; margin-top: 0; border-bottom: 2px solid #c41e3a; padding-bottom: 6px; }
h2 { font-size: 14pt; margin-top: 22px; color: #8b1538; page-break-after: avoid; }
h3 { font-size: 12pt; margin-top: 16px; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code, pre { font-family: Menlo, Monaco, Consolas, monospace; font-size: 9pt; }
pre {
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  border-radius: 6px;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-word;
  page-break-inside: avoid;
}
code { background: #f4f4f5; padding: 1px 4px; border-radius: 3px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10pt; page-break-inside: avoid; }
th, td { border: 1px solid #d4d4d8; padding: 6px 8px; text-align: left; }
th { background: #fafafa; }
hr { border: none; border-top: 1px solid #e4e4e7; margin: 20px 0; }
ul, ol { padding-left: 1.4em; }
a { color: #8b1538; text-decoration: none; }
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    src: Path = args.input
    out: Path = args.output or src.with_suffix(".pdf")
    text = src.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="utf-8"/>
  <title>{src.stem}</title>
  <style>{CSS}</style>
</head>
<body>{body}</body>
</html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(
            path=str(out),
            format="A4",
            print_background=True,
            margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
        )
        browser.close()

    print(out)


if __name__ == "__main__":
    main()
