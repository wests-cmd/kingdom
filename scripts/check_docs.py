#!/usr/bin/env python3
"""Check the six current navigation documents using only the Python standard library.

Checks local Markdown inline/reference links, repository containment, exact path
case and the nine README headings. It does not crawl historical reports, fetch
external URLs, validate fragments, or parse HTML links.
"""
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote, urlsplit

DOCUMENTS = ("README.md", "docs/README.md", "docs/ARCHITECTURE.md",
             "docs/DEVELOPMENT.md", "docs/OPERATIONS.md", "docs/PROJECT_STATUS.md")
SECTIONS = ("Overview", "Project map", "Run locally", "Configuration",
            "Verification", "Operations and updates", "Integrations",
            "Status and roadmap", "Documentation")


def visible_markdown(text):
    """Mask code examples while preserving line numbers for diagnostics."""
    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is None and marker:
            fence = marker[1]
            lines.append("\n" if line.endswith("\n") else "")
        elif fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            lines.append("\n" if line.endswith("\n") else "")
        else:
            lines.append(line)
    return re.sub(r"(`+)(.*?)\1", lambda m: "\n" * m[0].count("\n"),
                  "".join(lines), flags=re.S)


def destination(text, start):
    """Read an inline destination, including angle paths and balanced parentheses."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start < len(text) and text[start] == "<":
        end = text.find(">", start + 1)
        return text[start + 1:end] if end >= 0 else None
    result, depth, index = [], 0, start
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] in "() \\":
            index += 1
            result.append(text[index])
        elif char == "(":
            depth += 1
            result.append(char)
        elif char == ")":
            if depth == 0:
                return "".join(result)
            depth -= 1
            result.append(char)
        elif char.isspace() and depth == 0:
            return "".join(result)
        else:
            result.append(char)
        index += 1
    return None


def markdown_links(text):
    references = {}
    for match in re.finditer(r"^ {0,3}\[([^]\n]+)\]:[ \t]*(.*)$", text, re.M):
        value = destination(match[2] + ")", 0)
        if value is not None:
            references[" ".join(match[1].lower().split())] = value
    for match in re.finditer(r"!?\[[^]\n]*\]\(", text):
        value = destination(text, match.end())
        if value is None:
            yield match.start(), None
        else:
            yield match.start(), value
    for match in re.finditer(r"!?\[([^]\n]+)\](?:\[([^]\n]*)\])?", text):
        following = text[match.end():match.end() + 1]
        if following in ("(", ":"):
            continue
        label = match[2] if match[2] else match[1]
        key = " ".join(label.lower().split())
        if match[2] is not None and key not in references:
            yield match.start(), None
        elif key in references:
            yield match.start(), references[key]


def local_target(root, document, target):
    if target is None:
        return "malformed or undefined Markdown link", False
    if target.startswith("#"):
        return None, False  # Anchor validation is deliberately out of scope.
    try:
        parts = urlsplit(target)
    except ValueError:
        return "invalid link URL", False
    if parts.scheme.lower() in {"http", "https", "mailto"}:
        return None, False
    if parts.scheme or parts.netloc:
        return "unsupported or absolute link scheme", False
    path = unquote(parts.path)
    if not path:  # Empty destination refers to this document.
        return None, False
    if "\\" in path or PurePosixPath(path).is_absolute():
        return "use a relative repository path with forward slashes", True
    current = document.parent
    for component in PurePosixPath(path).parts:
        if component == "..":
            current = current.parent
            if not current.is_relative_to(root):
                return "link escapes the repository", True
            continue
        if component == ".":
            continue
        try:
            names = [entry.name for entry in current.iterdir()]
        except OSError:
            return "link parent is missing or unreadable", True
        if component not in names:
            if any(name.casefold() == component.casefold() for name in names):
                return "link path case differs from the actual file/directory", True
            return "link target does not exist", True
        current = current / component
        if not current.resolve().is_relative_to(root):
            return "link resolves outside the repository", True
    return None, True


def main():
    root = Path(__file__).resolve().parents[1]
    errors, count = [], 0
    for name in DOCUMENTS:
        document = root / name
        if not document.is_file() or not document.resolve().is_relative_to(root):
            errors.append(f"{name}: required document is missing or outside the repository")
            continue
        try:
            text = visible_markdown(document.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError):
            errors.append(f"{name}: document cannot be read as UTF-8")
            continue
        if name == "README.md":
            headings = re.findall(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", text, re.M)
            for title in SECTIONS:
                if headings.count(title) != 1:
                    errors.append(f"{name}: expected exactly one '## {title}' heading")
        for offset, target in markdown_links(text):
            error, local = local_target(root, document, target)
            count += int(local)
            if error:
                line = text.count("\n", 0, offset) + 1
                errors.append(f"{name}:{line}: {error}: {target!r}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"DOCS PASS: {len(DOCUMENTS)} documents, {count} relative links; README sections present.")
    print("Scope: external URLs, fragments and HTML links are not validated; historical reports are not crawled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
