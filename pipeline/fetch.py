"""
STEP 1 - get the raw data.

For this tracker the authoritative dataset is HAND-CURATED: data/events.csv is
the truth, edited by a person against a primary source document. There is no
upstream feed that emits "data-center policy events", so fetch() does not go
out to the internet for the published rows.

What fetch() does today is copy the curated file into the raw scratch area, so
the rest of the pipeline reads from one place.

Candidate harvesting is a SEPARATE step (pipeline/harvest.py), kept out of the
four-step pipeline on purpose: it talks to the network and to the Claude API,
and it must never be able to change what gets published. It writes only to
data/candidates.csv. A person promotes rows into events.csv with
pipeline/review.py. That gate is why the dataset is citable.
"""
import shutil

from common import DATA, load_config

RAW = DATA / "raw" / "events.csv"


def fetch():
    cfg = load_config()
    src = DATA / cfg.get("events_file", "events.csv")

    if not src.exists():
        raise SystemExit(f"FAIL: {src} does not exist - the curated dataset is missing")

    RAW.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, RAW)
    print(f"using curated dataset {src.name}")
    return RAW


if __name__ == "__main__":
    fetch()
