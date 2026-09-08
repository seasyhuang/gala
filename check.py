#!/usr/bin/env python3
"""Watch KCC Notices for a K-Pop Gala call; Discord on new matches."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

LIST_URL = "https://canada.korean-culture.org/en/1117/board/580/list"
STATE_PATH = Path(__file__).resolve().parent / "notified.txt"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Recall-first: any of these title-adjacent patterns counts.
PATTERNS = [
    re.compile(
        r"gala.{0,100}call\s+for.{0,40}(?:dancers?|teams?)"
        r"|call\s+for.{0,40}(?:dancers?|teams?).{0,100}gala",
        re.I | re.S,
    ),
    re.compile(
        r"gala.{0,100}(?:registration|registr\w*|apply|application|audition)"
        r"|(?:registration|registr\w*|apply|application|audition).{0,100}gala",
        re.I | re.S,
    ),
    re.compile(
        r"k-?pop\s*gala.{0,120}(?:dancers?|teams?|call)"
        r"|(?:dancers?|teams?|call).{0,120}k-?pop\s*gala",
        re.I | re.S,
    ),
    re.compile(
        r"\[[^\]]{0,80}gala[^\]]{0,80}\].{0,80}(?:call|dancers?|teams?)"
        r"|(?:call|dancers?|teams?).{0,80}\[[^\]]{0,80}gala[^\]]{0,80}\]",
        re.I | re.S,
    ),
]

PAST_YEAR = re.compile(r"2024|2025")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def fetch_html(url: str) -> str:
    # CloudFront sets kinx-sign-id then 302s to the same URL; cookies required.
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with opener.open(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def find_hits(html: str) -> list[tuple[str, str]]:
    """Return (normalized_snippet, context_for_year_check) pairs."""
    seen: set[str] = set()
    hits: list[tuple[str, str]] = []
    for pattern in PATTERNS:
        for match in pattern.finditer(html):
            snippet = normalize(match.group(0))
            if len(snippet) > 240:
                snippet = snippet[:240].rstrip() + "…"
            if not snippet or snippet in seen:
                continue
            # Wider window so 2024/2025 in the title still exclude partial spans.
            start = max(0, match.start() - 60)
            end = min(len(html), match.end() + 60)
            context = normalize(html[start:end])
            seen.add(snippet)
            hits.append((snippet, context))
    # Drop fragments that are substrings of a longer hit.
    snippets = [s for s, _ in hits]
    keep = []
    for snippet, context in hits:
        if any(snippet != other and snippet in other for other in snippets):
            continue
        keep.append((snippet, context))
    return keep


def load_notified(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        normalize(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def classify(
    hits: list[tuple[str, str]], notified: set[str]
) -> tuple[list[str], list[str], list[str]]:
    excluded: list[str] = []
    already: list[str] = []
    new: list[str] = []
    for snippet, context in hits:
        if PAST_YEAR.search(context):
            excluded.append(snippet)
        elif snippet in notified or any(
            snippet in n or n in snippet for n in notified
        ):
            already.append(snippet)
        else:
            new.append(snippet)
    return excluded, already, new


def print_report(
    hits: list[tuple[str, str]],
    excluded: list[str],
    already: list[str],
    new: list[str],
    dry_run: bool,
) -> None:
    mode = "dry-run" if dry_run else "live"
    print(f"URL: {LIST_URL}")
    print(f"Mode: {mode}")
    print(f"Raw hits: {len(hits)}")
    for snippet, _ in hits:
        print(f"  - {snippet}")
    print(f"Excluded (2024/2025): {len(excluded)}")
    for hit in excluded:
        print(f"  - {hit}")
    print(f"Already notified: {len(already)}")
    for hit in already:
        print(f"  - {hit}")
    label = "Would notify" if dry_run else "Notify"
    print(f"{label}: {len(new)}")
    for hit in new:
        print(f"  - {hit}")


def notify_discord(webhook: str, hit: str) -> None:
    payload = {
        "content": (
            "**Possible KCC Gala call detected**\n"
            f"{hit}\n"
            f"{LIST_URL}"
        )
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def append_notified(path: Path, hits: list[str]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for hit in hits:
            f.write(hit + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches only; never Discord or write notified.txt",
    )
    args = parser.parse_args()

    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    dry_run = args.dry_run or not webhook

    try:
        html = fetch_html(LIST_URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        return 1

    hits = find_hits(html)
    notified = load_notified(STATE_PATH)
    excluded, already, new = classify(hits, notified)
    print_report(hits, excluded, already, new, dry_run=dry_run)

    if dry_run:
        if args.dry_run:
            print("Dry-run: skipped Discord and state write.")
        else:
            print("No DISCORD_WEBHOOK_URL: skipped Discord and state write.")
        return 0

    for hit in new:
        try:
            notify_discord(webhook, hit)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"Discord failed for hit: {exc}", file=sys.stderr)
            return 1

    if new:
        append_notified(STATE_PATH, new)
        print(f"Appended {len(new)} hit(s) to {STATE_PATH.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
