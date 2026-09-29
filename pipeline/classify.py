"""
THE CLASSIFIER — the editorial judgment, applied at volume.

One question, asked of every candidate headline:

    Does this describe a concrete action by a government body or regulated
    utility affecting data-center development, or is it commentary about
    data centers?

That distinction is the whole product. "Goldwater Institute says Pima County's
moratorium is unlawful" and "Pima County adopts a moratorium" are the same
subject and opposite answers.

What this file is NOT allowed to do: write to events.csv. It annotates
candidates so a person can review the plausible ones first. Its verdict is a
sort order, not a fact.

Two things worth knowing about the implementation:

  * The controlled vocabularies from config.json are compiled into the JSON
    schema as enums, so the model physically cannot return a policy_type that
    validate_data.py would later reject.
  * The rubric is a cached system prompt and the headlines go in the user turn,
    so repeated runs pay ~10% on the stable half.

Needs ANTHROPIC_API_KEY. Without it, harvest still runs on the prefilter alone.
"""
import json

CHUNK = 25          # headlines per request — keeps output well inside max_tokens
MAX_TOKENS = 16000

RUBRIC = """\
You are triaging news headlines for a public database of government and utility \
actions affecting U.S. data-center development. The database is cited by \
reporters, so precision matters more than recall at this stage — a human \
reviews everything you mark as an action.

Classify each headline as exactly one verdict:

"action" — a government body or regulated utility took, or is formally \
considering, a concrete step. Ordinances, zoning votes, moratoria, permits \
granted or denied, tax agreements, PUC orders, tariff filings, bills \
introduced or passed, court rulings on any of these. Scheduling a public \
hearing or formally proposing something counts: the process step is the event.

"commentary" — discussion, opinion, advocacy, analysis, polling, or a \
corporate announcement with no government action attached. An advocacy group \
calling a moratorium illegal is commentary. A company announcing a new campus \
is commentary. A think tank's report is commentary. These are the most common \
false positives — be strict.

"unclear" — the headline genuinely does not say. Do not guess to be helpful; \
"unclear" is a useful answer and costs a human ten seconds.

Then, for actions only, extract what the headline actually supports. Leave a \
field as "" when the headline does not state it. Do not infer a state from an \
outlet's name, do not guess a status from a verb tense, and never invent a \
docket number. An empty field is correct; a plausible wrong one is expensive, \
because it is what the human sees first and may not re-check.

confidence is your certainty in the verdict, 0.0 to 1.0.
rationale is at most 12 words, explaining the verdict.
summary is a neutral one-sentence restatement of the action, no adjectives.\
"""


def _schema(vocab):
    """Controlled vocabularies become enums — invalid values are unrepresentable."""
    def enum(name):
        return {"type": "string", "enum": [""] + list(vocab.get(name, []))}

    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "verdict": {"type": "string", "enum": ["action", "commentary", "unclear"]},
            "confidence": {"type": "number"},
            "rationale": {"type": "string"},
            "state": {"type": "string",
                      "description": "Two-letter USPS code, or '' if not stated"},
            "gov_level": enum("gov_level"),
            "policy_type": enum("policy_type"),
            "status": enum("status"),
            "summary": {"type": "string"},
        },
        "required": ["id", "verdict", "confidence", "rationale", "state",
                     "gov_level", "policy_type", "status", "summary"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"results": {"type": "array", "items": item}},
        "required": ["results"],
        "additionalProperties": False,
    }


def classify(items, cfg):
    """Annotate candidate dicts in place. Silently degrades to prefilter-only."""
    try:
        import anthropic
    except ImportError:
        print("  anthropic not installed — leaving candidates unclassified")
        return items

    # Don't gate on ANTHROPIC_API_KEY alone: the SDK also resolves
    # ANTHROPIC_AUTH_TOKEN, an `ant auth login` profile, and WIF env vars.
    try:
        client = anthropic.Anthropic()
    except Exception as e:
        print(f"  no usable credentials ({type(e).__name__}) — leaving candidates unclassified")
        return items
    model = cfg.get("harvest", {}).get("model", "claude-opus-5-5")
    schema = _schema(cfg.get("vocab", {}))
    by_id = {it["candidate_id"]: it for it in items}
    done = 0

    for i in range(0, len(items), CHUNK):
        batch = items[i:i + CHUNK]
        listing = "\n".join(
            f'{it["candidate_id"]}\t{it["title"]}\t[outlet: {it.get("outlet", "")}]'
            for it in batch)

        try:
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": "medium",
                               "format": {"type": "json_schema", "schema": schema}},
                system=[{"type": "text", "text": RUBRIC,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content":
                           "Classify each headline. Return one result per id.\n\n" + listing}],
            )
        except TypeError as e:
            # SDK raises TypeError (not AuthenticationError) when it cannot
            # resolve any credential while building the request headers.
            if "authentication" not in str(e).lower():
                raise
            print("  no credentials — set ANTHROPIC_API_KEY or run `ant auth login`")
            break
        except anthropic.AuthenticationError:
            print("  credentials rejected — check ANTHROPIC_API_KEY")
            break
        except anthropic.RateLimitError:
            print("  rate limited — stopping early, candidates kept unclassified")
            break
        except anthropic.APIStatusError as e:
            print(f"  API error {e.status_code} — stopping early: {e.message}")
            break
        except anthropic.APIConnectionError:
            print("  network error — stopping early, candidates kept unclassified")
            break

        if resp.stop_reason == "refusal":
            print("  request refused — skipping this batch")
            continue

        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            results = json.loads(text)["results"]
        except (json.JSONDecodeError, KeyError, TypeError):
            print("  unparseable response — skipping this batch")
            continue

        for r in results:
            it = by_id.get(r.get("id"))
            if not it:
                continue
            it.update({
                "verdict": r.get("verdict", ""),
                "confidence": round(float(r.get("confidence") or 0), 2),
                "rationale": r.get("rationale", ""),
                "proposed_state": (r.get("state") or "").upper(),
                "proposed_gov_level": r.get("gov_level", ""),
                "proposed_policy_type": r.get("policy_type", ""),
                "proposed_status": r.get("status", ""),
                "proposed_summary": r.get("summary", ""),
            })
            done += 1

        u = resp.usage
        print(f"  batch {i // CHUNK + 1}: {len(results)} classified "
              f"({u.input_tokens} in / {u.output_tokens} out, "
              f"{u.cache_read_input_tokens} cached)")

    actions = sum(1 for it in items if it.get("verdict") == "action")
    print(f"classified {done}/{len(items)} — {actions} look like real actions")
    return items
