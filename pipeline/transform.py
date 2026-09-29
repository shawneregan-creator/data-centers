"""
STEP 2 - turn the curated events into exactly what the site needs.

Normalising, deriving, and counting go here. It produces:

  data/site_data.csv   the published dataset, one row per event
  data/meta.json       row count, update date, provenance, and facet counts
"""
import json
from datetime import datetime, timezone

import pandas as pd

from common import DATA, load_config, write_json
from fetch import RAW

TEXT_COLS = ["state", "gov_level", "policy_type", "status", "resource_issue",
             "date_precision", "verified"]

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "US": "Federal",
}


def transform():
    cfg = load_config()
    df = pd.read_csv(RAW, dtype=str).fillna("")

    # --- normalise ------------------------------------------------------
    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()
    df["state"] = df["state"].str.upper()

    df["justification"] = (df["justification"].str.strip().str.lower()
                           .str.replace(r"\s*;\s*", ";", regex=True))

    # --- derive ---------------------------------------------------------
    dates = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = dates.dt.year.astype("Int64").astype(str).replace("<NA>", "")
    df["month"] = dates.dt.strftime("%Y-%m").fillna("")
    df["state_name"] = df["state"].map(STATE_NAMES).fillna(df["state"])
    # Keep as a clean string: 150 rather than 150.0, blank rather than NaN.
    _mw = pd.to_numeric(df["mw_threshold"], errors="coerce")
    df["mw_threshold"] = _mw.map(lambda v: "" if pd.isna(v) else format(v, "g"))

    # Newest first - this is a news-shaped dataset.
    df = df.assign(_sort=dates).sort_values("_sort", ascending=False,
                                            na_position="last").drop(columns="_sort")

    # --- publish gate ---------------------------------------------------
    # curated_rows is the size of the dataset a person maintains. rows is what
    # actually ships. The breakage guard watches the former, because holding
    # rows back is a policy decision, not a broken source.
    curated_rows = len(df)
    if cfg.get("require_verified"):
        df = df[df["verified"] == "yes"]
        if len(df) < curated_rows:
            print(f"require_verified: held back {curated_rows - len(df)} unverified row(s)")

    out = DATA / "site_data.csv"
    df.to_csv(out, index=False)

    def counts(col):
        s = df[col][df[col] != ""]
        return s.value_counts().to_dict()

    # Snapshot the PREVIOUS row count before we overwrite meta.json, so
    # validate_data.py has something real to compare today's count against.
    meta_path = DATA / "meta.json"
    previous_curated = None
    if meta_path.exists():
        previous_curated = json.loads(meta_path.read_text()).get("curated_rows")

    write_json(meta_path, {
        "rows": int(len(df)),
        "curated_rows": int(curated_rows),
        "previous_curated_rows": previous_curated,
        "unverified": int((df["verified"] != "yes").sum()),
        "threads": int(df["thread_id"].replace("", pd.NA).nunique()),
        "updated": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "updated_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_name": cfg["source_name"],
        "source_url": cfg["source_url"],
        "facets": {c: counts(c) for c in
                   ["state", "gov_level", "policy_type", "status", "resource_issue"]},
        "by_month": counts("month"),
    })

    print(f"wrote {len(df)} rows to data/site_data.csv")
    return df


if __name__ == "__main__":
    transform()
