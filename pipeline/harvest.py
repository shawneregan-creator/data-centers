"""
CANDIDATE HARVEST — discovery, not truth.

Scans news feeds for stories that might describe a government or utility action
affecting data-center development, and writes them to data/candidates.csv for a
person to review.

Nothing in this file may write to data/events.csv. That gate is the reason the
dataset is worth citing. The harvester's job is to stop you missing things, not
to decide what is true — a candidate is a lead, and the human who promotes it
reads the primary source document, not the headline.

Three stages, cheapest first:

  1. fetch      — pull Google News RSS for each query in config.json
  2. prefilter  — keyword gate, free, drops the obvious noise
  3. classify   — Claude reads what survives (optional; see classify.py)

Run it on its own:  python pipeline/harvest.py
"""
import csv
import hashlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from common import DATA, load_config

CANDIDATES = DATA / "candidates.csv"

COLS = ["candidate_id", "found_date", "published", "title", "url", "outlet", "query",
        "prefilter_hits", "verdict", "confidence", "rationale", "proposed_state",
        "proposed_gov_level", "proposed_policy_type", "proposed_status",
        "proposed_summary", "review_status"]

RSS = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en"
UA = "Mozilla/5.0 (compatible; data-center-policy-tracker/1.0)"


# --------------------------------------------------------------------------
# 1. fetch
# --------------------------------------------------------------------------
def fetch_feed(query, timeout=30):
    """One Google News RSS query -> list of raw item dicts."""
    url = RSS.format(urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()

    items = []
    for it in ET.fromstring(raw).iterfind(".//item"):
        def text(tag):
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        items.append({
            "title": text("title"),
            "url": text("link"),
            "published": text("pubDate"),
            "outlet": text("source"),
            "query": query,
        })
    return items


# --------------------------------------------------------------------------
# 2. prefilter — free, and it removes most of the volume
# --------------------------------------------------------------------------
def prefilter(item, cfg):
    """
    Cheap keyword gate. Must mention a data center AND at least one word that
    suggests a government action happened. Returns the matched action words, or
    None to drop.

    Deliberately loose: a false positive costs one line in a review queue, a
    false negative means the event is never seen again.
    """
    h = cfg["harvest"]
    hay = item["title"].lower()
    if not any(k in hay for k in h["must_match_any"]):
        return None
    hits = [w for w in h["action_words"] if re.search(r"\b" + re.escape(w), hay)]
    return hits or None


def within_lookback(item, days):
    try:
        pub = datetime.strptime(item["published"], "%a, %d %b %Y %H:%M:%S %Z")
    except (ValueError, KeyError):
        return True  # unparseable date: keep it, let the human decide
    return pub.replace(tzinfo=timezone.utc) >= datetime.now(timezone.utc) - timedelta(days=days)


# --------------------------------------------------------------------------
# dedup
# --------------------------------------------------------------------------
def canonical(url):
    """Strip tracking noise so the same story from two queries collapses."""
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    keep = [(k, v) for k, v in urllib.parse.parse_qsl(u.query)
            if not k.startswith(("utm_", "oc")) and k not in ("ved", "usg")]
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path.rstrip("/"),
                                    urllib.parse.urlencode(keep), ""))


def candidate_id(item):
    return hashlib.sha1(canonical(item["url"]).encode()).hexdigest()[:12]


def _column(path, *names):
    """Values from the named columns of a CSV, if the file exists."""
    if not path.exists():
        return set()
    out = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for n in names:
                if row.get(n, "").strip():
                    out.add(canonical(row[n].strip()))
    return out


def already_known():
    """URLs already in the published dataset or already sitting in the queue."""
    seen = _column(DATA / "events.csv", "source_url", "secondary_url")
    seen |= _column(CANDIDATES, "url")
    return seen


def load_existing():
    if not CANDIDATES.exists():
        return []
    with open(CANDIDATES, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def harvest(classify_fn=None):
    cfg = load_config()
    h = cfg.get("harvest", {})
    if not h.get("enabled"):
        print("harvest: disabled in config.json")
        return []

    seen = already_known()
    fresh, dropped, dupes = [], 0, 0

    for q in h["queries"]:
        try:
            items = fetch_feed(q)[: h.get("max_items_per_query", 40)]
        except Exception as e:                      # one bad feed must not kill the run
            print(f"  ! query failed ({q}): {type(e).__name__}: {e}")
            continue

        for it in items:
            if not it["url"] or canonical(it["url"]) in seen:
                dupes += 1
                continue
            if not within_lookback(it, h.get("lookback_days", 14)):
                continue
            hits = prefilter(it, cfg)
            if not hits:
                dropped += 1
                continue
            seen.add(canonical(it["url"]))
            it["candidate_id"] = candidate_id(it)
            it["prefilter_hits"] = ";".join(hits)
            fresh.append(it)

        print(f"  {q[:44]:<46} {len(items):>3} items")

    print(f"harvest: {len(fresh)} new, {dropped} failed prefilter, {dupes} already known")

    if fresh and classify_fn:
        print(f"classifying {len(fresh)} candidates...")
        classify_fn(fresh, cfg)

    rows = load_existing()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for it in fresh:
        rows.append({c: it.get(c, "") for c in COLS} | {
            "candidate_id": it["candidate_id"],
            "found_date": now,
            "review_status": it.get("review_status", "new"),
        })

    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    pending = sum(1 for r in rows if r.get("review_status") == "new")
    print(f"data/candidates.csv: {len(rows)} rows, {pending} awaiting review")
    return fresh


if __name__ == "__main__":
    try:
        from classify import classify
    except ImportError:
        classify = None
        print("note: classify.py unavailable — running prefilter only")
    harvest(classify_fn=classify)
