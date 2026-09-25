"""Splice legend.md into README.md, next to the map.

    python scripts/build_readme.py

Edit legend.md (plain markdown), run this, and the legend beside the map on the
repo's main page is updated. Text between the two markers in README.md is
replaced; everything else in README.md is left alone.
"""
import re
import sys

from common import ROOT

README = ROOT / "README.md"
LEGEND = ROOT / "legend.md"
START, END = "<!-- legend:start -->", "<!-- legend:end -->"


def main():
    legend = LEGEND.read_text(encoding="utf-8")
    legend = re.sub(r"<!--.*?-->", "", legend, flags=re.S).strip()  # drop editor notes

    for path in re.findall(r"\]\(([^)\s]+)\)", legend):  # warn about broken swatch links
        if not path.startswith(("http://", "https://")) and not (ROOT / path).exists():
            print(f"warning: legend.md links to missing file: {path}", file=sys.stderr)

    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        sys.exit(f"README.md is missing the {START} / {END} markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    README.write_text(f"{head}{START}\n\n{legend}\n\n{END}{tail}", encoding="utf-8")
    print("README.md updated from legend.md")


if __name__ == "__main__":
    main()
