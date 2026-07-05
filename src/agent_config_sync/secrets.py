import re

SECRET_PATTERNS = [
    # High-confidence vendor prefixes (no false positives in prose).
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{32,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # Quoted assignment: key = "value".
    re.compile(
        r"(?i)(?:[a-z0-9_]*[_-])?(?:key|secret|token|password|passwd)\s*[:=]\s*"
        r"['\"][^'\"]{8,}['\"]"
    ),
    # Unquoted assignment in markdown prose. Require the value to contain a digit
    # so plain words ("token: documentation") are not flagged as secrets.
    re.compile(
        r"(?i)(?:[a-z0-9_]*[_-])?(?:api[_-]?key|key|secret|token|password|passwd)"
        r"\s*[:=]\s*(?=[A-Za-z0-9_\-./+=]*\d)[A-Za-z0-9_\-./+=]{12,}"
    ),
]


class SecretFoundError(Exception):
    def __init__(self, runtime: str, matches: list[str]):
        self.runtime = runtime
        self.matches = matches
        super().__init__(f"secret-like content for runtime '{runtime}'")


def find_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            hits.append(match.group(0))
    return hits
