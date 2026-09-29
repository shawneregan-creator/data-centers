"""
STEP 3 - refuse to publish something broken.

For a dataset meant to be cited, the vocabularies ARE the data quality. A
typo'd status ("aproved") silently drops a row out of every filter on the
site, and nobody notices. So every controlled field is checked against
config.json here.

Add a check whenever you find a new way the data can be wrong.
"""
import json
import sys

import pandas as pd

from common import DATA, load_config

REQUIRED = ["event_id", "date", "state", "gov_level", "policy_type", "status", "summary"]
SINGLE_VALUED = ["gov_level", "policy_type", "status", "resource_issue", "date_precision", "verified"]


def validate():
    cfg = load_config()
    vocab = cfg.get("vocab", {})
    path = DATA / "site_data.csv"

    if not path.exists():
        raise SystemExit("FAIL: data/site_data.csv does not exist")

    df = pd.read_csv(path, dtype=str).fillna("")
    problems = []

    if df.empty:
        problems.append("the dataset is empty")

    # --- structure ------------------------------------------------------
    for col in REQUIRED:
        if col not in df.columns:
            problems.append(f"missing required column: {col}")
    if problems:
        _fail(problems)

    for col in REQUIRED:
        blank = df.index[df[col].str.strip() == ""].tolist()
        if blank:
            problems.append(f"{len(blank)} row(s) have no {col} (first at row {blank[0] + 2})")

    # --- identity -------------------------------------------------------
    dupes = df["event_id"][df["event_id"].duplicated()].unique().tolist()
    if dupes:
        problems.append(f"duplicate event_id: {', '.join(dupes[:5])}")

    # --- controlled vocabularies ----------------------------------------
    for col in SINGLE_VALUED:
        allowed = set(vocab.get(col, []))
        if not allowed or col not in df.columns:
            continue
        bad = sorted(set(df[col][(df[col] != "") & (~df[col].isin(allowed))]))
        if bad:
            problems.append(f"{col} has values outside the vocabulary: {', '.join(bad)}")

    # justification is multi-valued, semicolon-separated
    allowed = set(vocab.get("justification", []))
    if allowed and "justification" in df.columns:
        seen = {v for cell in df["justification"] for v in cell.split(";") if v}
        bad = sorted(seen - allowed)
        if bad:
            problems.append(f"justification has values outside the vocabulary: {', '.join(bad)}")

    # --- dates ----------------------------------------------------------
    parsed = pd.to_datetime(df["date"], errors="coerce")
    unparsed = df["date"][parsed.isna() & (df["date"] != "")].tolist()
    if unparsed:
        problems.append(f"unparseable date(s): {', '.join(unparsed[:5])} (use YYYY-MM-DD)")
    future = parsed[parsed > pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(days=365)]
    if len(future):
        problems.append(f"{len(future)} row(s) dated more than a year in the future")

    # --- numerics -------------------------------------------------------
    if "mw_threshold" in df.columns:
        mw = pd.to_numeric(df["mw_threshold"], errors="coerce")
        bad_mw = df["mw_threshold"][(df["mw_threshold"] != "") & mw.isna()].tolist()
        if bad_mw:
            problems.append(f"non-numeric mw_threshold: {', '.join(bad_mw[:5])}")

    # --- citability -----------------------------------------------------
    if "verified" in df.columns and "source_url" in df.columns:
        cited = df[df["verified"] == "yes"]
        missing = cited.index[cited["source_url"].str.strip() == ""].tolist()
        if missing:
            problems.append(
                f"{len(missing)} row(s) marked verified=yes but have no source_url "
                f"(first at row {missing[0] + 2})")
        bad_url = df["source_url"][(df["source_url"] != "") &
                                   (~df["source_url"].str.startswith(("http://", "https://")))]
        if len(bad_url):
            problems.append(f"source_url is not a URL: {', '.join(bad_url.tolist()[:3])}")

    # --- a broken source should not silently gut the site ----------------
    # Compare the CURATED count, not the published one: require_verified
    # deliberately holds rows back, and that must not look like breakage.
    meta_path = DATA / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        previous = meta.get("previous_curated_rows")
        current = meta.get("curated_rows", len(df))
        if previous and current < previous * 0.5:
            problems.append(
                f"curated row count fell from {previous} to {current} - "
                "that looks like a broken source, not real change")

    if problems:
        _fail(problems)

    unverified = int((df.get("verified", pd.Series(dtype=str)) != "yes").sum())
    print(f"validation passed: {len(df)} rows", end="")
    print(f" ({unverified} still unverified)" if unverified else "")
    return df


def _fail(problems):
    print("VALIDATION FAILED:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    validate()
