#!/usr/bin/env python3
"""Lightweight secret and personal-data scanner.

pre-commit passes the staged files; CI (or anyone) can scan every tracked
file with ``python scripts/scan_secrets.py --all-tracked``. The commit or job
is blocked when a likely credential or a personal-data dump is detected.

Detected: provider API keys, JWTs (Supabase service_role / anon keys),
database URLs with an inline password, hard-coded defaults for secret env
vars or ``--password`` options, password literals in code, Django fixtures
or SQL dumps of user/account tables, and files with many email addresses.

A reviewed false positive can be suppressed by putting
``pragma: allowlist secret`` on the same line (the detect-secrets marker).
"""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
import re
import subprocess
import sys

ALLOW_MARKER = "pragma: allowlist secret"

# Provider-specific token formats: reported wherever they appear.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenRouter key", re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}")),
    ("ElevenLabs key", re.compile(r"sk_[A-Za-z0-9]{20,}")),
    ("Groq key", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("Gemini key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Cerebras key", re.compile(r"csk-[A-Za-z0-9]{20,}")),
    ("HuggingFace key", re.compile(r"hf_[A-Za-z0-9]{20,}")),
    ("Together key", re.compile(r"tgp_v1_[A-Za-z0-9_-]{20,}")),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("OpenAI/DeepSeek-style key", re.compile(r"\bsk-(?!or-v1-)[A-Za-z0-9_-]{32,}")),
    ("NVIDIA key", re.compile(r"nvapi-[A-Za-z0-9_-]{20,}")),
    ("Supabase secret key", re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}")),
    ("Supabase access token", re.compile(r"\bsbp_[A-Za-z0-9]{30,}")),
    ("Razorpay live key id", re.compile(r"rzp_live_[A-Za-z0-9]{10,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
]

JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")

DB_URL = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?)(?:\+[a-z0-9]+)?://"
    r"[^\s:/@'\"`]+:(?P<value>[^\s@'\"`]+)@(?P<host>[^\s:/'\"`?]+)"
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1", "host.docker.internal"}

# Env var names that END in a secret-ish suffix (TOKEN_MODEL or DAILY_TOKENS do not).
_SECRET_NAME = r"[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|SECRET_KEY|TOKEN|API_?KEY|PRIVATE_KEY|SERVICE_ROLE_KEY|ACCESS_KEY)"
SECRET_ENV_DEFAULT = re.compile(
    r"(?:getenv|environ\.get|env\.get)\(\s*[\"'](?P<name>" + _SECRET_NAME + r")[\"']\s*,\s*"
    r"(?:default\s*=\s*)?[\"'](?P<value>[^\"']+)[\"']"
    r"|process\.env\.(?P<jsname>" + _SECRET_NAME + r")\s*(?:\|\||\?\?)\s*[\"'`](?P<jsvalue>[^\"'`]+)[\"'`]"
)
CLI_SECRET_DEFAULT = re.compile(
    r"(?i)add_argument\(\s*[\"']--?[\w-]*(?:password|passwd|secret|token|api[-_]?key)[\w-]*[\"']"
    r"[^)\n]*?\bdefault\s*=\s*[\"'](?P<value>[^\"']+)[\"']"
)
PASSWORD_LITERAL = re.compile(
    r"(?i)[\"']?\b(?:[a-z0-9]+_)*pass(?:word|wd)\b[\"']?\s*[:=]\s*[\"'](?P<value>[^\"'\s]{6,})[\"']"
)
PASSWORD_PROSE = re.compile(
    r"(?i)\bpassword\s*(?:is\s+|=\s*|:\s*)?\s[`'\"]?(?P<value>[^\s`'\"<>{}()\[\]]{6,64})"
)

# Personal-data dumps (file-level checks).
USER_FIXTURE_MODEL = re.compile(  # case-insensitive: custom exporters write "accounts.Subscription"
    r"(?i)\"model\"\s*:\s*\"(?P<model>accounts\.(?:customuser|userdevice|paymentattempt|subscription|tokentransaction)"
    r"|auth\.user|sessions\.session|axes\.access(?:log|attempt|failurelog))\""
)
USER_TABLE_SQL = re.compile(
    r"(?i)\b(?:INSERT\s+INTO|COPY)\s+(?:\"?public\"?\.)?\"?(?P<table>accounts_[a-z_]+|auth_user|django_session|axes_[a-z_]+)\b"
)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
EMAIL_DUMP_THRESHOLD = 10
MAX_FINDINGS_PER_LABEL = 5  # per file; the rest are summarised
NON_PERSONAL_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "test.com", "local.test", "localhost")

PLACEHOLDER = re.compile(
    r"(?i)(your|xxx|example|placeholder|changeme|change[-_]me|dummy|fake|sample|redacted|"
    r"insecure|mock|local|test|\.\.\.|\*\*\*|<|>|\{|\}|\[|\]|\$|%\()"
)
PROSE_SKIP_SUFFIXES = {".md", ".markdown", ".rst", ".txt", ".adoc"}
CODE_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".sh", ".bash", ".ps1", ".psm1", ".bat", ".cmd",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".json", ".env", ".example", ".gs",
}
TEST_DIRS = {"tests", "test", "e2e", "__tests__", "fixtures", "testdata"}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".ico",
    ".woff",
    ".woff2",
    ".mp4",
    ".mp3",
    ".webm",
    ".sqlite3",
}


def _mask(token: str) -> str:
    """Never reveal short secrets (passwords): only long tokens show a type prefix."""
    if len(token) < 20:
        return f"<{len(token)} chars>"
    return f"{token[:4]}...{token[-2:]} ({len(token)} chars)"


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.search(value)) or bool(re.fullmatch(r"[A-Z0-9_]+", value))


def _looks_like_secret(value: str) -> bool:
    """A non-placeholder value with letters and digits (or a long random-looking string)."""
    if len(value) < 6 or _is_placeholder(value) or value.lower() in {"true", "false", "none", "null"}:
        return False
    has_letter = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return (has_letter and has_digit) or (len(value) >= 20 and " " not in value)


def _looks_like_password(value: str) -> bool:
    """Letters plus digits, and an uppercase letter or a symbol (not an identifier)."""
    if not 6 <= len(value) <= 64 or _is_placeholder(value):
        return False
    if value.startswith("!") or re.match(r"[a-z0-9_]+\$", value):
        return False  # Django unusable-password marker or hash; dumps are flagged as a whole
    has_letter = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    has_upper_or_symbol = any(c.isupper() for c in value) or any(c in "!@#^&*+=?~-" for c in value)
    return has_letter and has_digit and has_upper_or_symbol


def _jwt_label(token: str) -> str:
    try:
        segment = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
    except (ValueError, binascii.Error, IndexError):
        return "JSON Web Token"
    role = claims.get("role") if isinstance(claims, dict) else None
    if role == "service_role":
        return "Supabase service_role key (JWT)"
    if role == "anon":
        return "Supabase anon key (JWT; keep it in env config)"
    return "JSON Web Token"


def _is_test_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = parts[-1] if parts else ""
    if any(part in TEST_DIRS for part in parts[:-1]):
        return True
    return name.startswith(("test_", "tests_", "test.", "tests.")) or bool(
        re.search(r"(_tests?\.py|\.(spec|test)\.[cm]?[jt]sx?)$", name)
    )


def _scan_line(line: str, *, code: bool, prose: bool) -> list[tuple[str, str]]:
    """(label, masked value) for each distinct secret value on one line."""
    findings: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: str, raw: str) -> None:
        if raw not in seen:
            seen.add(raw)
            findings.append((label, _mask(raw)))

    for label, pattern in PATTERNS:
        for match in pattern.finditer(line):
            if "XXXX" not in match.group(0).upper():
                add(label, match.group(0))
    for match in JWT.finditer(line):
        add(_jwt_label(match.group(0)), match.group(0))
    for match in DB_URL.finditer(line):
        value, host = match.group("value"), match.group("host").lower()
        if (
            host in LOCAL_HOSTS
            or len(value) < 6
            or _is_placeholder(value)
            or value.lower() in {"password", "postgres"}
        ):
            continue
        add("Database URL with inline password", value)
    for match in SECRET_ENV_DEFAULT.finditer(line):
        name = match.group("name") or match.group("jsname")
        value = match.group("value") or match.group("jsvalue")
        if _looks_like_secret(value):
            add(f"Hard-coded default for {name}", value)
    for match in CLI_SECRET_DEFAULT.finditer(line):
        if _looks_like_secret(match.group("value")):
            add("Hard-coded default for a secret CLI option", match.group("value"))
    if code:
        for match in PASSWORD_LITERAL.finditer(line):
            if _looks_like_password(match.group("value")):
                add("Password literal", match.group("value"))
    if prose:
        for match in PASSWORD_PROSE.finditer(line):
            if _looks_like_password(match.group("value")):
                add("Password in text", match.group("value"))
    return findings


def _read_text(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            head = fh.read(4096)
    except OSError:
        return None
    encoding = "utf-8"
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"  # e.g. PowerShell `>` output; must not be skipped as binary
    elif b"\x00" in head:
        return None
    try:
        return path.read_text(encoding=encoding, errors="ignore")
    except OSError:
        return None


def _scan_file(path: Path, rel: Path | None = None) -> list[tuple[int, str, str]]:
    """Scan one file; ``rel`` (repo-relative path) decides test/doc classification."""
    if not path.exists() or not path.is_file():
        return []
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return []
    text = _read_text(path)
    if text is None:
        return []

    rel = rel or path
    suffix = rel.suffix.lower()
    is_code = (suffix in CODE_SUFFIXES or rel.name in {"Procfile", "Dockerfile"} or rel.name.startswith(".env"))
    is_code = is_code and not _is_test_path(rel)
    prose = is_code and suffix not in PROSE_SKIP_SUFFIXES and suffix != ".json"

    findings: list[tuple[int, str, str]] = []
    per_label: dict[str, int] = {}
    emails: set[str] = set()
    first_email_line = 0
    models: dict[str, int] = {}
    tables: dict[str, int] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for label, masked in _scan_line(line, code=is_code, prose=prose):
            per_label[label] = per_label.get(label, 0) + 1
            if per_label[label] <= MAX_FINDINGS_PER_LABEL:
                findings.append((line_number, label, masked))
        for m in USER_FIXTURE_MODEL.finditer(line):
            models.setdefault(m.group("model").lower(), line_number)
        for m in USER_TABLE_SQL.finditer(line):
            tables.setdefault(m.group("table").lower(), line_number)
        for address in EMAIL.findall(line):
            address = address.lower()
            if address.endswith(NON_PERSONAL_EMAIL_DOMAINS):
                continue
            if address not in emails:
                emails.add(address)
                first_email_line = first_email_line or line_number
    for label, count in per_label.items():
        if count > MAX_FINDINGS_PER_LABEL:
            findings.append((0, f"{label}: {count - MAX_FINDINGS_PER_LABEL} more not shown", "-"))
    if models:
        findings.append((min(models.values()), "Personal-data dump: Django fixture rows for " + ", ".join(sorted(models)), "-"))
    if tables:
        findings.append((min(tables.values()), "Personal-data dump: SQL rows for " + ", ".join(sorted(tables)), "-"))
    if len(emails) >= EMAIL_DUMP_THRESHOLD:
        findings.append((first_email_line, f"Possible personal-data dump: {len(emails)} distinct email addresses", "-"))
    return findings


def _tracked_files() -> list[tuple[Path, Path]]:
    """(absolute path, repo-relative path) for every file in the git index."""
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [(root / name, Path(name)) for name in out.decode("utf-8", "replace").split("\0") if name]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--all-tracked" in args:
        targets = _tracked_files()
    else:
        targets = [(Path(arg), Path(arg)) for arg in args if arg and not arg.startswith("-")]
    if not targets:
        return 0

    all_findings: list[tuple[Path, int, str, str]] = []
    for path, rel in targets:
        for line_no, label, masked in _scan_file(path, rel):
            all_findings.append((rel, line_no, label, masked))

    if not all_findings:
        return 0

    print("Secret scan failed. Potential credentials or personal data detected:")
    for path, line_no, label, masked in all_findings:
        print(f"  - {path}:{line_no} [{label}] {masked}")

    print(
        "\nMove secrets to environment variables and rotate exposed credentials before committing; "
        "keep personal-data dumps out of the repository. For a reviewed false positive add "
        f"'{ALLOW_MARKER}' to the line."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
