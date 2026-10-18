"""The minimal P-12 literal gate: no personal literals or infrastructure identifiers in the repo.

Scans every tracked file and every untracked file that git does not ignore (``git ls-files --cached
--others --exclude-standard``) for:

- ``email``: e-mail addresses, except the reserved example domains and GitHub noreply addresses;
- ``phone``: phone numbers (international ``+`` form, ``tel:`` links, separated national forms);
- ``domain``: host names outside ``ALLOWED_DOMAINS`` (in URLs and bare in text);
- ``ipv4``: IPv4 addresses outside the documentation ranges, loopback and ``0.0.0.0``;
- ``private-host``: private host-name patterns (``.local``, ``.lan``, ``.internal``, tailnet and
  tunnel hosts, single-label URL hosts, NetBIOS-style machine names, UNC paths, ssh targets);
- ``home-path``: user home paths that name a real account;
- ``name``: person-like names in fixtures (``tests/fixtures/``, ``src/coflow/contracts/examples/``)
  that are not in ``tests/fixtures/synthetic/allowed_names.txt``.

Findings print as ``path:line: category: masked literal`` (masked, because CI logs are public) and
the exit code is 1; a clean tree exits 0. Tune the allow-lists below, never the categories. Known
limit: a four-part version number that is also a valid public IPv4 address is reported; write it
with a ``v`` prefix or quote it differently.

**The owner's deny-list** (P-12) is the private part: ``--deny-list PATH`` (default: the
``COFLOW_DENY_LIST`` environment variable; skipped when neither is set, so CI is unchanged). The
file lives outside every repository and holds keyed hashes only, never the phrases::

    {"key_file": "<a path outside any repository>", "digests": ["<hex>", ...]}

Every line is normalised (NFC, casefold, whitespace collapsed) and split into word tokens; each
1- to 4-token gram of ``DENY_MIN_CHARS`` characters or more is hashed with
``hmac(key, gram, sha256)``, and a gram whose digest is listed is a ``deny`` finding (masked like
the others). The digests are made by a generator that lives with the owner's data, never in a
repository, with the same ``deny_grams`` normalisation. Installed as a local pre-push hook::

    #!/bin/sh
    exec python tools/literal_gate.py --deny-list "$COFLOW_DENY_LIST"

Run from the repository root:  python tools/literal_gate.py [--deny-list PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES_FILE = ROOT / "tests" / "fixtures" / "synthetic" / "allowed_names.txt"
FIXTURE_DIRS = ("tests/fixtures/", "src/coflow/contracts/examples/")
FIXTURE_SUFFIXES = {".json", ".yaml", ".yml", ".csv", ".txt", ".sql", ".html", ".xml"}

# ------------------------------------------------------------------------------------- allow-lists

# Every public host the repository names on purpose. A host is allowed when it equals an entry or
# is a subdomain of one. Reserved names (RFC 2606 and 6761) are allowed by RESERVED_TLDS.
ALLOWED_DOMAINS = frozenset(
    {
        # reserved example domains
        "example.com",
        "example.org",
        "example.net",
        # code hosting, CI and the package index
        "github.com",
        "githubusercontent.com",
        "ghcr.io",
        "pypi.org",
        "pythonhosted.org",
        "python.org",
        # tools and standards the docs and code cite
        "astral.sh",
        "json-schema.org",
        "developercertificate.org",
        "apache.org",
        "docker.com",
        "sigstore.dev",
        "telegram.org",
        # official sources named by the tax-pack design
        "boe.es",
        "agenciatributaria.gob.es",
        # the project's public episode videos (DEVLOG)
        "youtu.be",
    }
)
RESERVED_TLDS = frozenset({"example", "test", "invalid", "localhost"})
ALLOWED_EMAIL_DOMAINS = frozenset({"example.com", "example.org", "example.net"})
ALLOWED_EMAILS = frozenset({"noreply@github.com", "git@github.com"})
NOREPLY = re.compile(r"^[\w.+-]+@users\.noreply\.github\.com$", re.I)
ALLOWED_IPV4 = (
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("0.0.0.0/32"),  # "any" in bind examples
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
)
# Account names that are placeholders, not people.
ALLOWED_HOME_USERS = frozenset(
    {"user", "username", "you", "runner", "name", "owner", "example", "me", "someone"}
)
# Single-label host names the docs use as generic placeholders (DEPLOYMENT's ssh recipes).
ALLOWED_PLACEHOLDER_HOSTS = frozenset({"localhost", "coflow-host", "host", "server"})

# ---------------------------------------------------------------------------------------- patterns

# TLDs checked for bare host names in text. File extensions and module names that are also TLDs
# (py, md, sh, app, zip, mov, rs, pl, date, ...) are deliberately absent: those hosts are still
# caught inside URLs and e-mail addresses, which accept any TLD.
BARE_TLDS = (
    "com|org|net|io|dev|ai|energy|cloud|tech|info|biz|xyz|site|online|eu|de|es|fr|uk|ru|ua|by|"
    "kz|nl|ch|cz|se|fi|dk|pt|gr|tr|il|cn|jp|kr|us|ca|au|nz|br|mx|ar|co|me|tv|gg|ly|ts\\.net"
)
PRIVATE_SUFFIXES = (
    "local|lan|internal|intranet|corp|home|localdomain|home\\.arpa|ts\\.net|tailscale\\.net|"
    "trycloudflare\\.com|ngrok\\.io|ngrok-free\\.app|ngrok\\.app"
)
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_END = r"(?![\w-]|\.[A-Za-z0-9])"

EMAIL = re.compile(r"(?<![\w.%+-])[\w.%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}" + _END)
PHONE_INTL = re.compile(r"(?<![\w+/=.%-])\+\d{1,3}(?:[ .\-]?\(?\d{1,4}\)?){2,6}(?![\w-])")
PHONE_TEL = re.compile(r"\btel:\+?[\d\-. ()]{6,}", re.I)
PHONE_NATIONAL = re.compile(r"(?<![\w.+-])\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\w.-])")
URL = re.compile(r"\b[a-z][a-z0-9+.-]{1,15}://(?:[^\s/@'\"<>()]+@)?([^\s/?#'\"<>()\[\]`*|]+)", re.I)
BARE_HOST = re.compile(rf"(?<![\w.@/\\-])((?:{_LABEL}\.)+(?:{BARE_TLDS})){_END}")
PRIVATE_HOST = re.compile(rf"(?<![\w.@/\\-])((?:{_LABEL}\.)+(?:{PRIVATE_SUFFIXES})){_END}")
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d]|\.\d)")
NETBIOS = re.compile(r"\b(?:DESKTOP|LAPTOP|WIN|PC)-[A-Z0-9]{5,15}\b")
UNC = re.compile(r"(?<![\w\\])\\\\([A-Za-z][\w.-]*)\\[\w$.-]+")
SSH_TARGET = re.compile(r"\b(?:ssh|scp|sftp|rsync|mosh)\b[^\n]*?[\s\"']([\w.-]+@([\w.<>-]+))")
HOME_PATH = re.compile(
    r"(?:\b[A-Za-z]:\\{1,2}Users\\{1,2}|(?<![\w.])/home/|/Users/)([A-Za-z][\w.-]*)"
)
LATIN_NAME = re.compile(r"\b[A-Z][a-z]+(?:[ -][A-Z][a-z]+)+\b")
DENY_ENV = "COFLOW_DENY_LIST"
DENY_MIN_CHARS = 6
DENY_MAX_TOKENS = 4
DENY_TOKEN = re.compile(r"\w+")
CYRILLIC_NAME = re.compile(r"\b[А-ЯЁ][а-яё]+(?:[ -][А-ЯЁ][а-яё]+)*\b")


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    line: int
    category: str
    literal: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.category}: {mask(self.literal)}"


def mask(text: str) -> str:
    """Show only the first three characters: CI logs are public."""
    return text[:3] + "*" * max(len(text) - 3, 0)


# ----------------------------------------------------------------------------------------- checks


def domain_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host.rsplit(".", 1)[-1] in RESERVED_TLDS:
        return True
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def ipv4_allowed(text: str) -> bool | None:
    """True or False for a valid IPv4 address; None for a string that is not one."""
    try:
        addr = ipaddress.IPv4Address(text)
    except ValueError:
        return None
    return any(addr in net for net in ALLOWED_IPV4)


def _placeholder(host: str) -> bool:
    # <host>, {host}, $HOST, %HOST%, or an upper-case placeholder such as CORE_HOST
    return any(c in host for c in "<>{}$%") or (host.upper() == host and "_" in host)


def check_url_host(raw: str) -> tuple[str, str] | None:
    host = raw.replace("\\", "").rstrip(".,;:!")
    if ":" in host and not host.startswith("["):
        host = host.split(":", 1)[0]
    if not host or _placeholder(host) or host.lower() in ALLOWED_PLACEHOLDER_HOSTS:
        return None
    allowed_ip = ipv4_allowed(host)
    if allowed_ip is not None:
        return None if allowed_ip else ("ipv4", host)
    if "." not in host:
        return ("private-host", host)
    if PRIVATE_HOST.fullmatch(host.lower()):
        return ("private-host", host)
    return None if domain_allowed(host) else ("domain", host)


def _digits(text: str) -> int:
    return sum(c.isdigit() for c in text)


def scan_line(
    line: str, *, fixture: bool = False, names: frozenset[str] = frozenset()
) -> Iterator[tuple[str, str]]:
    """Yield (category, literal) for every finding on one line."""
    emails = []
    for m in EMAIL.finditer(line):
        email = m.group(0)
        emails.append(m.span())
        domain = email.rsplit("@", 1)[1].lower()
        if (
            email.lower() in ALLOWED_EMAILS
            or NOREPLY.match(email)
            or any(domain == d or domain.endswith("." + d) for d in ALLOWED_EMAIL_DOMAINS)
            or domain.rsplit(".", 1)[-1] in RESERVED_TLDS
        ):
            continue
        yield ("email", email)

    for pattern in (PHONE_INTL, PHONE_NATIONAL):
        for m in pattern.finditer(line):
            if 8 <= _digits(m.group(0)) <= 15:
                yield ("phone", m.group(0))
    for m in PHONE_TEL.finditer(line):
        yield ("phone", m.group(0))

    url_spans = []
    for m in URL.finditer(line):
        url_spans.append(m.span())
        found = check_url_host(m.group(1))
        if found:
            yield found

    def outside(span: tuple[int, int]) -> bool:
        return not any(s <= span[0] < e for s, e in (*url_spans, *emails))

    for m in PRIVATE_HOST.finditer(line):
        if outside(m.span()):
            yield ("private-host", m.group(1))
    for m in BARE_HOST.finditer(line):
        host = m.group(1)
        if outside(m.span()) and not PRIVATE_HOST.fullmatch(host) and not domain_allowed(host):
            yield ("domain", host)

    for m in IPV4.finditer(line):
        if ipv4_allowed(m.group(1)) is False:
            yield ("ipv4", m.group(1))

    for m in NETBIOS.finditer(line):
        yield ("private-host", m.group(0))
    for m in UNC.finditer(line):
        if not _placeholder(m.group(1)):
            yield ("private-host", m.group(0))
    for m in SSH_TARGET.finditer(line):
        host = m.group(2)
        if _placeholder(host) or host.lower() in ALLOWED_PLACEHOLDER_HOSTS:
            continue
        if "." not in host or not domain_allowed(host):
            yield ("private-host", m.group(1))

    for m in HOME_PATH.finditer(line):
        user = m.group(1)
        if user.lower() not in ALLOWED_HOME_USERS and not _placeholder(user):
            yield ("home-path", m.group(0))

    if fixture:
        for pattern in (LATIN_NAME, CYRILLIC_NAME):
            for m in pattern.finditer(line):
                if m.group(0) not in names:
                    yield ("name", m.group(0))


# ------------------------------------------------------------------------------------ deny-list


@dataclass(frozen=True, slots=True)
class DenyList:
    """The owner's keyed digests (see the module docstring); the key never leaves its file."""

    key: bytes
    digests: frozenset[str]

    def digest(self, gram: str) -> str:
        return hmac.new(self.key, gram.encode("utf-8"), hashlib.sha256).hexdigest()


def deny_normalise(text: str) -> str:
    """NFC, casefold, whitespace collapsed: the form both the gate and the generator hash."""
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def deny_grams(text: str) -> Iterator[str]:
    """Every 1- to 4-token gram of ``text`` with ``DENY_MIN_CHARS`` characters or more."""
    tokens = DENY_TOKEN.findall(deny_normalise(text))
    for n in range(1, DENY_MAX_TOKENS + 1):
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i : i + n])
            if len(gram) >= DENY_MIN_CHARS:
                yield gram


def load_deny_list(path: Path, *, root: Path = ROOT) -> DenyList:
    """Read the deny-list file; its key file must lie outside this repository."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "key_file" not in data or "digests" not in data:
        raise ValueError("the deny-list holds {key_file, digests}")
    key_file = Path(str(data["key_file"])).expanduser().resolve()
    if key_file.is_relative_to(root.resolve()):
        raise ValueError("the deny-list key lies inside the repository")
    key = key_file.read_bytes().strip()
    if not key:
        raise ValueError("the deny-list key file is empty")
    digests = frozenset(str(d).strip().lower() for d in data["digests"])
    return DenyList(key=key, digests=digests)


def deny_hits(line: str, deny: DenyList) -> Iterator[str]:
    for gram in deny_grams(line):
        if deny.digest(gram) in deny.digests:
            yield gram


def load_names(path: Path = NAMES_FILE) -> frozenset[str]:
    if not path.exists():
        return frozenset()
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(s.strip() for s in lines if s.strip() and not s.lstrip().startswith("#"))


def is_fixture(rel: str) -> bool:
    return (
        rel.startswith(FIXTURE_DIRS)
        and Path(rel).suffix.lower() in FIXTURE_SUFFIXES
        and Path(rel).name != NAMES_FILE.name
    )


def scan_text(
    rel: str,
    text: str,
    names: frozenset[str] = frozenset(),
    deny: DenyList | None = None,
) -> list[Finding]:
    fixture = is_fixture(rel)
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        for category, literal in scan_line(line, fixture=fixture, names=names):
            out.append(Finding(rel, number, category, literal))
        if deny is not None:
            out += [Finding(rel, number, "deny", gram) for gram in deny_hits(line, deny)]
    return out


def repository_files(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return sorted({p for p in result.stdout.decode("utf-8").split("\0") if p})


def scan_files(
    rels: Iterable[str], root: Path = ROOT, deny: DenyList | None = None
) -> tuple[list[Finding], int]:
    names = load_names(root / NAMES_FILE.relative_to(ROOT))
    findings: list[Finding] = []
    scanned = 0
    for rel in rels:
        path = root / rel
        if not path.is_file():
            continue  # deleted in the working tree
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue  # binary
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(Finding(rel, 0, "encoding", "not UTF-8"))
            continue
        scanned += 1
        findings.extend(scan_text(rel, text, names, deny))
    return findings, scanned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The P-12 literal gate.")
    parser.add_argument(
        "--deny-list",
        default=os.environ.get(DENY_ENV) or None,
        help=f"the owner's keyed deny-list (default: ${DENY_ENV}; skipped when unset)",
    )
    args = parser.parse_args(argv)
    deny = None
    if args.deny_list:
        try:
            deny = load_deny_list(Path(args.deny_list))
        except (OSError, ValueError) as exc:
            print(f"literal gate: cannot read the deny-list: {exc}", file=sys.stderr)
            return 2
    try:
        files = repository_files()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"literal gate: cannot list files with git: {exc}", file=sys.stderr)
        return 2
    findings, scanned = scan_files(files, deny=deny)
    for finding in findings:
        print(finding.render())
    with_deny = f", deny-list of {len(deny.digests)} digests" if deny is not None else ""
    print(f"literal gate: {scanned} files scanned{with_deny}, {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
