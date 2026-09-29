"""
STEP 4 - render the site from the data.

Reads templates/index.html, fills it in, and writes site/. The site folder is
generated output: edit the template, not the result.

The whole dataset is embedded as JSON so filtering, search and the map run
client-side with no server and no API.
"""
import json
import math
import shutil

import pandas as pd
from jinja2 import Template

from common import DATA, SITE, TEMPLATES, load_config

# Columns the browser actually needs. Keeping this explicit stops the payload
# quietly doubling every time a bookkeeping column is added to the CSV.
WEB_COLS = ["event_id", "thread_id", "date", "date_precision", "state", "state_name",
            "locality", "gov_level", "actor", "policy_type", "status", "mw_threshold",
            "justification", "resource_issue", "docket_number", "summary",
            "source_url", "source_name", "secondary_url", "verified", "month", "year"]


def build():
    cfg = load_config()
    df = pd.read_csv(DATA / "site_data.csv", dtype=str).fillna("")
    meta = json.loads((DATA / "meta.json").read_text())

    for c in WEB_COLS:
        if c not in df.columns:
            df[c] = ""
    rows = df[WEB_COLS].to_dict(orient="records")

    html = Template((TEMPLATES / "index.html").read_text(encoding="utf-8")).render(
        cfg=cfg,
        meta=meta,
        rows=rows,
        vocab=cfg.get("vocab", {}),
        data_json=json.dumps(rows, separators=(",", ":")),
        facets_json=json.dumps(meta.get("facets", {}), separators=(",", ":")),
        months_json=json.dumps(meta.get("by_month", {}), separators=(",", ":")),
    )

    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html, encoding="utf-8")

    # The raw data, downloadable from the site.
    shutil.copy(DATA / "site_data.csv", SITE / "data.csv")

    for asset in ("favicon.svg", "preview.png", "apple-touch-icon.png"):
        src = TEMPLATES / asset
        if src.exists():
            shutil.copy(src, SITE / asset)

    kb = math.ceil((SITE / "index.html").stat().st_size / 1024)
    print(f"built site/index.html from {len(rows)} rows ({kb} KB)")


if __name__ == "__main__":
    build()
