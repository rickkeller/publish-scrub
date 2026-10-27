"""Read-only check before a public export. Does not edit files or print a full secret."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"}
TEXT_LIMIT = 1_000_000
HISTORY_LIMIT = 20_000_000
PLACEHOLDERS = {"example", "changeme", "placeholder", "redacted", "todo", "****", "your_password", "your_token"}


def mask(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + f" len={len(value)}"


def _patterns() -> list[tuple[str, re.Pattern[str]]]:
    home = "/" + "home" + "/"
    users = "/" + "Users" + "/"
    private_mark = "-" + "private"
    key_name = r"[A-Za-z0-9_.-]*(?:password|secret|api[_-]?key|token)[A-Za-z0-9_.-]*"
    quoted = r"['\"][^'\"]{8,}['\"]"
    bare = r"[^\s'\"]{8,}"
    return [
        ("github-token", re.compile(r"(?<![\w.])(?:ghp_|github_pat_)[A-Za-z0-9_]{8,}")),
        ("aws-key", re.compile(r"(?<![\w.])AKIA[A-Z0-9]{8,}")),
        ("slack-token", re.compile(r"(?<![\w.])xox[baprs]-[A-Za-z0-9-]{8,}")),
        ("openai-key", re.compile(r"(?<![\w.])sk-[A-Za-z0-9_-]{8,}")),
        ("slack-webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]{8,}")),
        ("private-key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
        ("db-url", re.compile(r"(?i)\b(?:postgres|postgresql|mysql|mongodb|redis)://[^:\s]+:[^@\s]+@")),
        ("bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b")),
        ("assignment", re.compile(rf"(?i)(?:^|[^\w])({key_name})\s*[:=]\s*({quoted}|{bare})")),
        ("chat-id", re.compile(r"(?i)\b(?:chat[_-]?id|user[_-]?id)\b\s*[:=]\s*['\"]?\d{8,}")),
        ("host-path", re.compile(re.escape(home) + r"\S+|" + re.escape(users) + r"\S+")),
        ("private-url", re.compile(r"github\.com/\S*" + re.escape(private_mark))),
    ]


def _assigned_value(kind: str, value: str) -> str:
    if kind != "assignment":
        return value
    parts = re.split(r"\s*[:=]\s*", value, maxsplit=1)
    return parts[1] if len(parts) == 2 else value


def _placeholder(value: str) -> bool:
    lowered = value.strip().strip("'\"").strip("<>").lower()
    if lowered in PLACEHOLDERS or lowered.startswith("your_"):
        return True
    if "${{" in value or "secrets." in lowered and lowered.startswith("${{"):
        return True
    return False


def _skip_match(kind: str, value: str, text: str, start: int) -> bool:
    if "${{" in text[max(0, start - 8): start + len(value) + 4]:
        return True
    if _placeholder(_assigned_value(kind, value)):
        return True
    if kind == "assignment" and "(" in _assigned_value(kind, value):
        return True
    if kind == "openai-key" and not any(ch.isdigit() for ch in value):
        return True
    if kind == "host-path":
        if start > 0 and text[start - 1] not in " \t\n\"'":
            return True
        segment = value.split("/", 3)[2] if value.count("/") >= 2 else ""
        if segment.isdigit():
            return True
    return False


def findings_in_text(text: str, where: str, line_no: int | None = None) -> list[str]:
    found = []
    for kind, pattern in _patterns():
        for match in pattern.finditer(text):
            value = match.group(0)
            if _skip_match(kind, value, text, match.start()):
                continue
            line = line_no if line_no is not None else text.count("\n", 0, match.start()) + 1
            found.append(f"{kind} {where}:{line} {mask(value)}")
    return found


def _read_text(data: bytes) -> str | None:
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if data.startswith(b"PK\x03\x04") or b"\0" in data[:8192]:
        return None
    return data.decode("utf-8")


def scan_tree(root: Path) -> tuple[list[str], list[str]]:
    found: list[str] = []
    unread: list[str] = []
    skipped: set[str] = set()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            skipped.update(part for part in rel.parts if part in SKIP_DIRS)
            continue
        if path.is_symlink() or not path.is_file():
            continue
        if path.stat().st_size > TEXT_LIMIT:
            unread.append(f"unread {rel}:1 file exceeds the text limit")
            continue
        if path.suffix.lower() == ".zip":
            unread.append(f"unread {rel}:1 zip was not opened")
            continue
        data = path.read_bytes()
        try:
            text = _read_text(data)
        except UnicodeDecodeError:
            text = None
        if text is None:
            unread.append(f"unread {rel}:1 file was not decoded")
            continue
        found.extend(findings_in_text(text, str(rel)))
    unread.extend(f"unread {name}:1 skipped directory" for name in sorted(skipped))
    return found, unread


def _history_findings(text: str) -> list[str]:
    sha = ""
    path = ""
    new_line = 1
    found: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("commit ") and len(raw.split()) >= 2:
            sha = raw.split()[1]
            path = ""
            continue
        if raw.startswith("diff --git "):
            parts = raw.split(" b/", 1)
            path = parts[1] if len(parts) == 2 else ""
            continue
        if raw.startswith("@@"):
            plus = raw.split("+", 1)
            num = plus[1].split(",")[0].split()[0] if len(plus) == 2 else "1"
            new_line = int(num) if num.lstrip("-").isdigit() else 1
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            found.extend(findings_in_text(raw[1:], f"{sha}:{path}", new_line))
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            found.extend(findings_in_text(raw[1:], f"{sha}:{path}", new_line))
    return found


def scan_history(root: Path) -> tuple[list[str], list[str], list[str]]:
    found: list[str] = []
    failures: list[str] = []
    unread: list[str] = []
    git = shutil.which("git")
    if git is None or not (root / ".git").exists():
        failures.append("git history was not scanned")
        return found, failures, unread
    try:
        result = subprocess.run(
            [git, "-C", str(root), "log", "-p", "--all", "-U0", "--no-color", "--pretty=format:commit %H"],
            capture_output=True,
            check=False,
        )
    except OSError:
        failures.append("git history was not scanned")
        return found, failures, unread
    if result.returncode != 0:
        failures.append("git history was not scanned")
        return found, failures, unread
    data = result.stdout
    if len(data) > HISTORY_LIMIT:
        failures.append("git history scan was truncated")
        return found, failures, unread
    text = data.decode("utf-8", errors="replace")
    found.extend(_history_findings(text))
    return found, failures, unread


def collect(root: Path, *, history: bool = True) -> tuple[list[str], list[str], list[str]]:
    found, unread = scan_tree(root)
    failures: list[str] = []
    if history:
        hist, failures, hist_unread = scan_history(root)
        found.extend(hist)
        unread.extend(hist_unread)
    return found, failures, unread


def scan(root: Path) -> list[str]:
    found, _failures, _unread = collect(root)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only check before a public export.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--no-history", action="store_true", help="Do not scan git history")
    args = parser.parse_args(argv)
    root = args.path.resolve()
    if not root.is_dir():
        print("not a directory", file=sys.stderr)
        return 2
    found, failures, unread = collect(root, history=not args.no_history)
    for line in unread:
        print(line)
    for line in found:
        print(line)
    for line in failures:
        print(line, file=sys.stderr)
    if failures:
        return 2
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
