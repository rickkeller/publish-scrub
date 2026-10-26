"""Read-only check before a public export. Does not edit files or print a full secret."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}
TEXT_LIMIT = 1_000_000
HISTORY_LIMIT = 20_000_000
PLACEHOLDERS = ("example", "changeme", "placeholder", "redacted", "your_", "todo", "****")


def mask(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + f" len={len(value)}"


def _patterns() -> list[tuple[str, re.Pattern[str]]]:
    home = "/" + "home" + "/"
    users = "/" + "Users" + "/"
    private_mark = "-" + "private"
    return [
        ("token", re.compile(r"\b(?:ghp_|github_pat_|AKIA|xox[baprs]-|sk-)[A-Za-z0-9_-]{8,}")),
        ("bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b")),
        ("assignment", re.compile(r"(?i)\b(?:password|secret|api[_-]?key|token)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
        ("chat-id", re.compile(r"(?i)\b(?:chat[_-]?id|user[_-]?id)\b\s*[:=]\s*['\"]?\d{8,}")),
        ("host-path", re.compile(re.escape(home) + r"\S+|" + re.escape(users) + r"\S+")),
        ("private-url", re.compile(r"github\.com/\S*" + re.escape(private_mark))),
    ]


def _placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(mark in lowered for mark in PLACEHOLDERS)


def findings_in_text(text: str, where: str) -> list[str]:
    found = []
    for kind, pattern in _patterns():
        for match in pattern.finditer(text):
            value = match.group(0)
            if _placeholder(value):
                continue
            line = text.count("\n", 0, match.start()) + 1
            found.append(f"{kind} {where}:{line} {mask(value)}")
    return found


def scan_tree(root: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.stat().st_size > TEXT_LIMIT:
            found.append(f"unread {path.relative_to(root)}:1 file exceeds the text limit")
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        found.extend(findings_in_text(text, str(path.relative_to(root))))
    return found


def scan_history(root: Path) -> list[str]:
    if not (root / ".git").exists():
        return ["history .:1 git history was not scanned"]
    result = subprocess.run(
        ["git", "-C", str(root), "log", "-p", "--all", "-U0", "--no-color"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ["history .:1 git history was not scanned"]
    text = result.stdout
    if len(text.encode()) > HISTORY_LIMIT:
        return ["history .:1 git history scan was truncated"]
    return findings_in_text(text, "history")


def scan(root: Path) -> list[str]:
    return scan_tree(root) + scan_history(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only check before a public export.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    root = args.path.resolve()
    if not root.is_dir():
        print("not a directory", file=sys.stderr)
        return 2
    found = scan(root)
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
