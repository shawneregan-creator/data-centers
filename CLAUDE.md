# Working in this repository

This is a small data site: a pipeline that refreshes a dataset on a schedule,
and a static page built from it, published to GitHub Pages. It was created from
the MI data-site template and lives in the author's own GitHub account.

## Layout

```
config.json           every setting a person edits by hand, plus the
                      controlled vocabularies every field is checked against
data/events.csv       THE DATASET — hand-curated, one row per event. The truth.
data/candidates.csv   machine-proposed rows awaiting human review (not published)
data/site_data.csv    generated — what the site actually shows
data/meta.json        generated — row count, update date, provenance
data/raw/             gitignored scratch space for downloads
pipeline/harvest.py   discovery — news feeds -> data/candidates.csv (NOT a
                      pipeline step; runs separately, cannot touch events.csv)
pipeline/classify.py  the editorial judgment, at volume: action vs commentary
pipeline/review.py    THE GATE — the only path from candidates into events
pipeline/fetch.py     step 1 — get the raw data
pipeline/transform.py step 2 — clean and shape it (most work happens here)
pipeline/validate_data.py  step 3 — refuse to publish something broken
pipeline/build_site.py     step 4 — render templates/ into site/
templates/index.html  the page source — EDIT THIS
site/                 generated output — DO NOT EDIT BY HAND
```

Run everything with `python pipeline/run_update.py`.

## What a row is

One row = one discrete action by a government body or regulated utility that
affects data-center development. An ordinance, bill, docket order, tariff
filing, or permit decision. Not commentary, not a corporate announcement, not
market news — unless it triggered a government action.

Rows about the same underlying fight share a `thread_id`, so the history of one
proposal can be read in order. Set it when the event is filed, not later.

Every controlled field (`gov_level`, `policy_type`, `status`, `resource_issue`,
`justification`, `date_precision`, `verified`) is checked against the vocabulary
in `config.json`. A typo does not produce a warning — it fails the build. This
is deliberate: a misspelled status silently vanishes from every filter on the
site, and nobody would notice.

## Conventions

- **Never edit `site/`.** It is regenerated on every run and your changes will
  be silently overwritten. Change `templates/index.html` instead.
- **Keep the four pipeline steps separate.** Fetching, transforming,
  validating, and rendering stay in their own files. Do not collapse them.
- **`config.json` is the only file a non-technical person should need to open.**
  If a new setting would be useful to them, add it there rather than hardcoding
  it in a script.
- **Add a validation check whenever you find a new way the data can be wrong.**
  A failing pipeline that keeps yesterday's good site is the desired behavior.
- Prefer stdlib and the three libraries already in `requirements.txt`. Ask
  before adding a dependency.

## Rules that are not negotiable

- **Never commit secrets.** API keys go in repository secrets and are read from
  the environment. If you find a key in a file, stop and say so.
- **Never put internal MI data in this repository.** No CRM exports, no donor
  records, no licensed or purchased datasets, nothing from Virtuous, Snowflake,
  or Piano. This repository is public and sits on a personal account, so there
  is no second pair of eyes. Published data must be public data the author is
  permitted to redistribute. If you are unsure about a file, stop and ask.
- **Never remove the provenance footer** — last updated, source, method note,
  CSV download. If the numbers are shown, their origin is shown with them.
- **Machine output never reaches `events.csv` on its own.** Automated scanning
  writes to `data/candidates.csv`; a person reads the primary source and
  promotes the row by hand. The value of this dataset is that every row was
  checked. Do not build anything that bypasses that gate.
- **A row is not publishable without a primary `source_url`.** `verified=yes`
  with an empty source fails validation. Set `require_verified: true` in
  config.json once the backlog is cleared, and unverified rows stop shipping.
- **Status is never color-coded.** Green-for-enacted / red-for-defeated encodes
  an editorial position on whether restricting data centers is good. Keep
  status in neutral ink. Color carries magnitude only.
- **Do not weaken `validate_data.py` to make a run pass.** If validation fails,
  the data or the transform is wrong. Fix that.

## The daily loop

    python pipeline/harvest.py        scan feeds, classify, fill the queue
    python pipeline/review.py list    triage — actions first, most confident first
    python pipeline/review.py show <id>
    python pipeline/review.py reject <id> [reason]
    python pipeline/review.py promote <id>    -> DRAFT row in events.csv
    # then edit events.csv: primary source_url, real summary, verified=yes
    python pipeline/run_update.py     validate and rebuild

`promote` never publishes. It drafts a row with `verified=no` and parks the
news link in `secondary_url`. The human finds the ordinance, bill, or docket
and puts THAT in `source_url`. A headline is a lead; the primary document is
the citation.

The classifier is a sort order, not a fact. Treat `verdict: action` as "worth
ten seconds", never as "true".

## Before the site is shared

Run `/publish` — see `.claude/commands/publish.md`.
