"""First-layer PR review: flag patterns that slip into AI-written or hurried code, and anything that leaks.

Reads the unified diff of the PR (added lines only) and prints GitHub annotations.
Exit 1 when a blocking rule hits; warnings never fail the build.

    git diff --unified=0 origin/main...HEAD | python scripts/ci/review_checks.py
"""
from __future__ import annotations

import re
import sys

# (rule, regex on an added line, file glob regex, blocking?, message)
RULES = [
    ("tls-off", r"verify\s*=\s*False|CERT_NONE|check_hostname\s*=\s*False|rejectUnauthorized:\s*false", r".*", True,
     "TLS verification disabled. Sources must be reached with verification on."),
    ("ua-spoof", r"Mozilla/5\.0|AppleWebKit|Chrome/\d", r"apps/collector/.*", True,
     "Browser User-Agent in a collector. OpenWatch identifies itself honestly and never spoofs a browser."),
    ("secret", r"(?i)(api[_-]?key|secret|token|passw(or)?d)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]", r".*", True,
     "Looks like a hardcoded credential. Keys belong in .env and are read from the environment."),
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r".*", True, "Private key material."),
    ("captcha", r"(?i)captcha|2captcha|anticaptcha|cloudscraper|undetected[_-]chromedriver", r"apps/.*", True,
     "Bot-wall / CAPTCHA circumvention isn't allowed. Leave blocked sources out."),
    ("placeholder", r"(?i)your[_-]?api[_-]?key|lorem ipsum|xxx+|<insert|replace[_ ]me|TODO: implement|NotImplementedError\(\)",
     r"apps/.*|packages/.*", True, "Placeholder left in code."),
    ("debug-print", r"^\s*print\(", r"apps/.*\.py|packages/.*\.py", False, "print() in app code: use the JSON logger."),
    ("console-log", r"console\.(log|debug)\(", r"apps/frontend/src/.*", False, "console.log left in UI code."),
    ("bare-except", r"except\s*:\s*$", r".*\.py", False, "Bare except: catch something specific."),
    ("swallow", r"except Exception:\s*pass", r"packages/.*|apps/api/.*", False, "Swallowed exception outside the collector."),
    ("plain-http", r"['\"]http://(?!localhost|127\.0\.0\.1|\[::1\])", r"apps/collector/.*", False,
     "Plain-HTTP source: prefer HTTPS when the source offers it."),
    ("keyed-source", r"key\s*=\s*['\"][A-Z0-9_]+['\"]", r"apps/collector/feeds/.*", False,
     "This feed needs an API key. OpenWatch prefers free, keyless sources: say in the PR why this one is worth it and confirm the key is free."),
    ("eval", r"\beval\(|\bexec\(|pickle\.loads|yaml\.load\((?!.*SafeLoader)", r".*\.py", True, "Unsafe eval/exec/deserialisation."),
    ("innerhtml", r"dangerouslySetInnerHTML|\.innerHTML\s*=", r"apps/frontend/src/.*", True, "Raw HTML injection in the UI (XSS risk)."),
]


def main() -> int:
    file, line_no, blocking = "", 0, 0
    for raw in sys.stdin:
        if raw.startswith("+++ "):
            file = raw[6:].strip() if raw.startswith("+++ b/") else ""
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
            continue
        if not raw.startswith("+") or raw.startswith("+++") or not file:
            continue
        text = raw[1:].rstrip("\n")
        if file.startswith(("tests/", "scripts/ci/")) or file.endswith((".md", ".lock", ".json")):
            line_no += 1
            continue
        for rule, pattern, where, block, msg in RULES:
            if re.fullmatch(where, file) and re.search(pattern, text) and "review-ok" not in text:
                level = "error" if block else "warning"
                print(f"::{level} file={file},line={line_no},title={rule}::{msg}")
                blocking += block
        line_no += 1
    print(f"review checks: {blocking} blocking finding(s)")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
