"""
One-off seeding script for the first real batch.

Two kinds of rows go in here, and the difference matters:

  VERIFIED — checked against a primary government source (gov.ca.gov,
  gov.texas.gov, energycommerce.house.gov, leginfo). verified=yes.

  DRAFT — promoted from the candidate queue on the strength of a headline.
  verified=no, news link in secondary_url, source_url deliberately EMPTY.
  These are leads with structure, not facts. A person still has to find the
  ordinance and fill source_url before they count.

Rows are only drafted where the state is unambiguous from the headline itself.
"Davidson County", "Scott County", "Forsyth County" and "St. Joseph County"
exist in several states, so those stay in the queue rather than get a guess.

Run once:  python scripts/seed_batch.py
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

EVENTS = ROOT / "data" / "events.csv"
CANDIDATES = ROOT / "data" / "candidates.csv"
TODAY = "2026-09-29"

CA = "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260"
CA_SIGNING = ("https://www.gov.ca.gov/2026/09/21/governor-newsom-signs-most-comprehensive-"
              "data-center-laws-in-the-nation-providing-communities-more-control-on-water-"
              "electricity-and-land-use/")

# --------------------------------------------------------------------------
# VERIFIED — primary government sources
# --------------------------------------------------------------------------
def ca_bill(num, author, title, policy_type, justification, resource):
    return dict(
        event_id=f"2026-09-21-ca-{num.lower().replace(' ', '')}",
        thread_id="ca-2026-data-center-package", date="2026-09-21", date_precision="day",
        state="CA", locality="Statewide", gov_level="state",
        actor=f"California Legislature ({author})", policy_type=policy_type,
        status="enacted", mw_threshold="", justification=justification,
        resource_issue=resource, docket_number=num,
        summary=f'{num} — "{title}". Signed 2026-09-21 as part of a seven-bill package.',
        source_url=CA + num.replace(" ", ""), source_name=f"California Legislative Information, {num}",
        secondary_url=CA_SIGNING, verified="yes", last_updated=TODAY)


VERIFIED = [
    dict(event_id="2026-09-16-us-hr9340-house-passage", thread_id="us-ratepayer-protection-act",
         date="2026-09-16", date_precision="day", state="US", locality="U.S. House",
         gov_level="federal", actor="U.S. House of Representatives",
         policy_type="ratepayer_protection", status="passed_one_chamber", mw_threshold="100",
         justification="ratepayer_cost", resource_issue="power", docket_number="H.R. 9340",
         summary=("House passed the Ratepayer Protection Act 417-3, requiring state public "
                  "utility commissions to set large-load standards for data centers above "
                  "100 MW so they pay the full incremental cost to serve their load."),
         source_url="https://energycommerce.house.gov/posts/ratepayer-protection-act-passes-house-with-strong-bipartisan-support",
         source_name="U.S. House Energy and Commerce Committee",
         secondary_url="https://www.utilitydive.com/news/house-passes-ratepayer-protection-bill-data-centers/830658/",
         verified="yes", last_updated=TODAY),

    dict(event_id="2026-09-21-tx-tceq-permit-halt", thread_id="tx-data-center-permit-pause",
         date="2026-09-21", date_precision="day", state="TX", locality="Statewide",
         gov_level="state", actor="Office of the Governor of Texas",
         policy_type="permitting", status="in_effect", mw_threshold="",
         justification="grid_reliability;water_use", resource_issue="both", docket_number="",
         summary=("Governor directed TCEQ to issue no permits sought by data center projects "
                  "pending completion of ERCOT and Texas Water Development Board audits. "
                  "TCEQ to report compliance by 2026-10-19."),
         source_url="https://gov.texas.gov/news/post/governor-abbott-directs-tceq-to-halt-data-center-permits",
         source_name="Office of the Texas Governor",
         secondary_url="https://www.keranews.org/texas-news/2026-09-22/gov-abbott-orders-tceq-to-pause-environmental-permits-for-data-centers-until-audit-is-complete",
         verified="yes", last_updated=TODAY),

    ca_bill("SB 1168", "McNerney", "Data centers: Rate structures",
            "utility_tariff", "ratepayer_cost", "power"),
    ca_bill("SB 886", "Padilla, McNerney", "California Technology Innovation and Ratepayer Protection Act",
            "ratepayer_protection", "ratepayer_cost", "power"),
    ca_bill("AB 2383", "Zbur", "Electricity: data centers",
            "utility_tariff", "ratepayer_cost", "power"),
    ca_bill("AB 2469", "Papan", "Data centers: water use disclosures",
            "transparency", "water_use;local_control", "water"),
    ca_bill("AB 2619", "Papan", "Water resources: data center",
            "water", "water_use", "water"),
    ca_bill("AB 1577", "Bauer-Kahan", "Data centers: reporting",
            "transparency", "environmental", "none"),
    ca_bill("SB 887", "Padilla",
            "California Environmental Quality Act: environmental leadership development "
            "projects: data centers: geothermal power plant projects",
            "permitting", "environmental", "power"),
]

# --------------------------------------------------------------------------
# DRAFTS — headline match -> structure. verified=no, source_url stays empty.
# (title substring, state, locality, gov_level, actor, policy_type, status,
#  justification, resource_issue)
# --------------------------------------------------------------------------
DRAFTS = [
    ("Pima County supervisors approve data center moratorium", "AZ", "Pima County", "county",
     "Pima County Board of Supervisors", "moratorium", "adopted", "local_control", "none"),
    ("Palm Beach County commissioners approve moratorium", "FL", "Palm Beach County", "county",
     "Palm Beach County Board of County Commissioners", "moratorium", "adopted", "land_use", "none"),
    ("Baltimore County extends data center moratorium", "MD", "Baltimore County", "county",
     "Baltimore County Council", "moratorium", "adopted", "land_use", "none"),
    ("Tulare County extends data center moratorium to 2027", "CA", "Tulare County", "county",
     "Tulare County Board of Supervisors", "moratorium", "adopted", "local_control", "none"),
    ("Spartanburg County joins other South Carolina counties", "SC", "Spartanburg County", "county",
     "Spartanburg County Council", "moratorium", "adopted", "land_use", "none"),
    ("Manatee County commissioners move forward with moratorium", "FL", "Manatee County", "county",
     "Manatee County Board of County Commissioners", "moratorium", "proposed", "land_use", "none"),
    ("Guilford County Board of Commissioners to consider moratorium", "NC", "Guilford County", "county",
     "Guilford County Board of Commissioners", "moratorium", "proposed", "land_use", "none"),
    ("Mesa County to consider data center moratorium", "CO", "Mesa County", "county",
     "Mesa County Board of Commissioners", "moratorium", "proposed", "land_use", "none"),
    ("Columbus County Considers a Moratorium", "NC", "Columbus County", "county",
     "Columbus County Board of Commissioners", "moratorium", "proposed", "land_use", "none"),
    ("City commissioners in Raton", "NM", "Raton", "municipal",
     "Raton City Commission", "moratorium", "rejected", "local_control", "none"),
    ("Cumberland Council Bans Data Centers in Zoning Ordinance on 6-1 Vote", "RI", "Cumberland", "municipal",
     "Cumberland Town Council", "zoning", "adopted", "land_use", "none"),
    ("Mercer County fiscal court rejects data center zoning ordinance", "KY", "Mercer County", "county",
     "Mercer County Fiscal Court", "zoning", "rejected", "local_control", "none"),
    ("Pocatello City Council votes to deny conditional use permit", "ID", "Pocatello", "municipal",
     "Pocatello City Council", "permitting", "rejected", "land_use", "none"),
    ("Augusta commission approves data center zoning ordinance - The Augusta Chronicle", "GA", "Augusta", "municipal",
     "Augusta Commission", "zoning", "adopted", "land_use", "none"),
    ("West Hazleton to vote on wide-ranging restrictions", "PA", "West Hazleton", "municipal",
     "West Hazleton Borough Council", "zoning", "proposed", "land_use", "none"),
    ("East Buffalo Township to vote on data center ordinance", "PA", "East Buffalo Township", "municipal",
     "East Buffalo Township Board of Supervisors", "zoning", "proposed", "land_use", "none"),
    ("Data centers face new rules in Saginaw", "MI", "Saginaw", "municipal",
     "Saginaw City Council", "zoning", "proposed", "land_use", "none"),
    ("Wisconsin Rapids data center denied", "WI", "Wisconsin Rapids", "municipal",
     "Wisconsin Rapids", "permitting", "rejected", "land_use", "none"),
    ("De Pere committee endorses data center moratorium on water burden", "WI", "De Pere", "municipal",
     "De Pere Common Council committee", "moratorium", "proposed", "water_use", "water"),
    ("Lombardo curtails Nevada data center tax break program", "NV", "Statewide", "state",
     "Office of the Governor of Nevada", "tax_incentive", "in_effect", "tax_base", "none"),
    ("Commission approves $240M in tax breaks for Indianapolis data center", "IN", "Indianapolis", "municipal",
     "Indianapolis Metropolitan Development Commission", "tax_incentive", "approved", "tax_base;jobs", "none"),
    ("Ferguson approves $1.8 billion data center project", "MO", "Ferguson", "municipal",
     "Ferguson City Council", "tax_incentive", "approved", "tax_base;jobs", "none"),
    ("Xcel Energy submits proposal to place large load tariffs", "CO", "Statewide", "utility",
     "Xcel Energy Colorado", "large_load_rules", "proposed", "ratepayer_cost", "power"),
    ("PUCT sets financial commitments for data center interconnection", "TX", "Statewide", "puc",
     "Public Utility Commission of Texas", "interconnection", "adopted", "grid_reliability;ratepayer_cost", "power"),
    ("Pennsylvania utility panel opens review", "PA", "Statewide", "puc",
     "Pennsylvania Public Utility Commission", "ratepayer_protection", "proposed", "ratepayer_cost", "power"),
    ("Judge rules Chatham County data center can proceed despite moratorium", "NC", "Chatham County", "county",
     "N.C. Superior Court", "moratorium", "rejected", "local_control", "none"),
]


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def pub_date(raw):
    """RSS pubDate -> YYYY-MM-DD. The REPORT date, not the action date."""
    try:
        return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return TODAY


def main():
    events = load(EVENTS)
    cols = list(events[0].keys())
    have = {r["event_id"] for r in events}
    cands = load(CANDIDATES)
    ccols = list(cands[0].keys())

    added = 0
    for row in VERIFIED:
        if row["event_id"] in have:
            continue
        assert set(row) == set(cols), set(row) ^ set(cols)
        events.append(row)
        added += 1
    print(f"verified rows added: {added}")

    drafted = 0
    for frag, state, locality, level, actor, ptype, status, just, res in DRAFTS:
        c = next((x for x in cands if frag.lower() in x["title"].lower()
                  and x["review_status"] == "new"), None)
        if not c:
            print(f"  ! no pending candidate for: {frag[:55]}")
            continue
        d = pub_date(c.get("published", ""))
        eid = f"DRAFT-{d}-{state.lower()}-{c['candidate_id'][:8]}"
        if eid in have:
            continue
        events.append({k: "" for k in cols} | dict(
            event_id=eid, thread_id=eid, date=d, date_precision="day",
            state=state, locality=locality, gov_level=level, actor=actor,
            policy_type=ptype, status=status, justification=just, resource_issue=res,
            summary=c["title"], source_url="", source_name="",
            secondary_url=c["url"], verified="no", last_updated=TODAY))
        c["review_status"] = "promoted"
        drafted += 1

    print(f"draft rows added:    {drafted}")
    save(EVENTS, events, cols)
    save(CANDIDATES, cands, ccols)
    print(f"events.csv now has  {len(events)} rows")


if __name__ == "__main__":
    main()
