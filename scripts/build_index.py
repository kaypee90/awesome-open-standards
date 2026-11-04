#!/usr/bin/env python3
"""Regenerate the README's category overview and A-Z index.

Both are built from the category tables, so a contributor only ever adds a
row to one table and then runs:

    python3 scripts/build_index.py          # rewrite README.md in place
    python3 scripts/build_index.py --check  # exit 1 if README.md is stale (CI)

It also fails if any category table is not in alphabetical order.
"""

import re
import sys
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

# Sections that hold standards tables sit between these two headings.
FIRST_NON_CATEGORY = {"A-Z Index", "Contributing"}

ROW = re.compile(r"^\| \[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\) \|")
HEADING = re.compile(r"^## (?P<title>.+)$")


def anchor(title):
    """GitHub's heading anchor: lowercase, drop punctuation, spaces to '-'."""
    slug = re.sub(r"[^\w\- ]", "", title.lower())
    return slug.replace(" ", "-")


def sort_key(name):
    """Case-insensitive, treating '-' like a space ("JSON-LD" < "JSON Schema")."""
    return name.lower().replace("-", " ")


def parse_categories(text):
    categories = []
    current = None
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            title = heading.group("title")
            if title in FIRST_NON_CATEGORY:
                break
            current = {"title": title, "names": []} if title != "Contents" else None
            if current:
                categories.append(current)
            continue
        row = ROW.match(line)
        if row and current:
            current["names"].append(row.group("name"))
    return [c for c in categories if c["names"]]


def check_order(categories):
    errors = []
    for cat in categories:
        expected = sorted(cat["names"], key=sort_key)
        if cat["names"] != expected:
            for got, want in zip(cat["names"], expected):
                if got != want:
                    errors.append(
                        f'"{cat["title"]}" table is not alphabetical: '
                        f'found "{got}" where "{want}" should be.'
                    )
                    break
    return errors


def build_overview(categories):
    total = sum(len(c["names"]) for c in categories)
    lines = [
        f"**{total} standards** in {len(categories)} categories.",
        "",
        "| Category | Standards | Includes |",
        "| --- | ---: | --- |",
    ]
    for cat in categories:
        examples = ", ".join(cat["names"][:4])
        more = ", ..." if len(cat["names"]) > 4 else ""
        lines.append(
            f'| [{cat["title"]}](#{anchor(cat["title"])}) '
            f'| {len(cat["names"])} | {examples}{more} |'
        )
    return "\n".join(lines)


def build_index(categories):
    entries = sorted(
        ((name, cat["title"]) for cat in categories for name in cat["names"]),
        key=lambda e: sort_key(e[0]),
    )
    by_letter = {}
    for name, title in entries:
        by_letter.setdefault(name[0].upper(), []).append(
            f"[{name}](#{anchor(title)})"
        )
    lines = ["| | Standards (links go to the category table) |", "| --- | --- |"]
    for letter, links in by_letter.items():
        lines.append(f"| **{letter}** | {' · '.join(links)} |")
    return "\n".join(lines)


def replace_block(text, name, body):
    pattern = re.compile(
        rf"(<!-- {name}:start [^\n]*-->\n).*?(<!-- {name}:end -->)", re.S
    )
    if not pattern.search(text):
        sys.exit(f"README.md is missing the <!-- {name}:start/end --> markers.")
    return pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)


def main():
    text = README.read_text(encoding="utf-8")
    categories = parse_categories(text)

    errors = check_order(categories)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    updated = replace_block(text, "overview", build_overview(categories))
    updated = replace_block(updated, "index", build_index(categories))

    if "--check" in sys.argv[1:]:
        if updated != text:
            print(
                "README.md overview/index is out of date. "
                "Run: python3 scripts/build_index.py",
                file=sys.stderr,
            )
            return 1
        print("README.md overview and index are up to date.")
        return 0

    README.write_text(updated, encoding="utf-8")
    print(f"Updated README.md ({sum(len(c['names']) for c in categories)} standards).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
