"""
THE GATE — the only path from candidates.csv into events.csv, and it runs
through a person.

    python pipeline/review.py list              pending candidates
    python pipeline/review.py list --all        including reviewed ones
    python pipeline/review.py show <id>         one candidate in full
    python pipeline/review.py reject <id> [why] not a government action
    python pipeline/review.py promote <id>      draft a row into events.csv

`promote` writes a DRAFT row: verified=no, the news URL parked in
secondary_url, and the fields the classifier guessed filled in. It does not
publish anything. You then open data/events.csv and do the part no machine
does — find the ordinance, bill, or docket itself, put THAT in source_url,
write the summary from the document rather than the headline, and set
verified=yes.

A news story is a lead. The primary source is the citation.
"""
import csv
import sys
from datetime import datetime, timezone

from common import DATA
from harvest import CANDIDATES, COLS

EVENTS = DATA / "events.csv"


def _load(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _find(rows, cid):
    for r in rows:
        if r["candidate_id"].startswith(cid):
            return r
    sys.exit(f"no candidate matching id {cid!r}")


def cmd_list(args):
    rows = _load(CANDIDATES)
    show_all = "--all" in args
    rows = [r for r in rows if show_all or r.get("review_status") == "new"]
    if not rows:
        print("nothing pending — run python pipeline/harvest.py")
        return
    # Most confident first: the classifier's best guesses are cheapest to judge.
    rows.sort(key=lambda r: (r.get("verdict") != "action", -_conf(r)))
    for r in rows:
        verdict = r.get("verdict") or "unclassified"
        conf = f"{_conf(r):.2f}" if r.get("confidence") else " -  "
        flag = {"action": "+", "commentary": ".", "unclear": "?"}.get(verdict, " ")
        print(f"{flag} {r['candidate_id']}  {conf}  {r['title'][:84]}")
        if r.get("rationale"):
            print(f"              {r['rationale'][:84]}")
    print(f"\n{len(rows)} shown.  promote <id> | reject <id> | show <id>")


def _conf(r):
    try:
        return float(r.get("confidence") or 0)
    except ValueError:
        return 0.0


def cmd_show(args):
    r = _find(_load(CANDIDATES), args[0])
    for k in COLS:
        if r.get(k):
            print(f"{k:>20}: {r[k]}")


def cmd_reject(args):
    rows = _load(CANDIDATES)
    r = _find(rows, args[0])
    r["review_status"] = "rejected"
    if len(args) > 1:
        r["rationale"] = " ".join(args[1:])
    _save(CANDIDATES, rows, COLS)
    print(f"rejected {r['candidate_id']}: {r['title'][:70]}")


def cmd_promote(args):
    cands = _load(CANDIDATES)
    c = _find(cands, args[0])

    events = _load(EVENTS)
    cols = list(events[0].keys()) if events else [
        "event_id", "thread_id", "date", "date_precision", "state", "locality",
        "gov_level", "actor", "policy_type", "status", "mw_threshold", "justification",
        "resource_issue", "docket_number", "summary", "source_url", "source_name",
        "secondary_url", "verified", "last_updated"]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = c["candidate_id"]
    draft = {k: "" for k in cols}
    draft.update({
        "event_id": f"DRAFT-{slug}",
        "thread_id": f"DRAFT-{slug}",
        "date": today,
        "date_precision": "day",
        "state": c.get("proposed_state", ""),
        "gov_level": c.get("proposed_gov_level", ""),
        "policy_type": c.get("proposed_policy_type", ""),
        "status": c.get("proposed_status", ""),
        "summary": c.get("proposed_summary") or c["title"],
        "secondary_url": c["url"],
        "source_name": c.get("outlet", ""),
        "verified": "no",
        "last_updated": today,
    })
    events.append(draft)
    _save(EVENTS, events, cols)

    c["review_status"] = "promoted"
    _save(CANDIDATES, cands, COLS)

    print(f"drafted DRAFT-{slug} into data/events.csv\n")
    print("  Now do the part the machine cannot:")
    print("   1. find the ordinance / bill / docket itself")
    print("   2. put that URL in source_url (the news link stays in secondary_url)")
    print("   3. rewrite summary from the document, not the headline")
    print("   4. set a real event_id and thread_id, check state/locality/date")
    print("   5. set verified=yes\n")
    print("  Validation will block a verified row with no source_url.")


def main():
    cmds = {"list": cmd_list, "show": cmd_show, "reject": cmd_reject, "promote": cmd_promote}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    args = sys.argv[2:]
    if sys.argv[1] in ("show", "reject", "promote") and not args:
        sys.exit(f"{sys.argv[1]} needs a candidate id")
    cmds[sys.argv[1]](args)


if __name__ == "__main__":
    main()
