"""Free diagnosis of a Part B run (no model calls).

Reads a committed Part B run (.json and its handoffs .jsonl), the frozen
ticket file and the kb_v1 articles, all read-only. Calls the retrieval
contract (open_retrieval, search, kb_info) only, which is local and free.

A. Grounding failures: every E-xx / P-xx code and number with a unit in
   each rejected draft, and where it appears.
B. "answer" tickets escalated as insufficient_context whose expected
   article was retrieved: the chunk kept for that article and the
   chunks of it that the diversity step dropped.
C. A summary of how many failures each cause would explain.

Usage:
    python -m evals.eval_diagnosis --run evals/reports/2026-10-17-part-b-run1.json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from evals.eval_experiments import WIDE_K, boost_queries, code_titles, diversify, merge
from evals.eval_tickets import REPO_ROOT, TICKETS_PATH

KB_DIR = REPO_ROOT / "data" / "kb_v1"
KB_VERSION = "v1"
TITLE_SEPARATOR = " — "


# --- kb_v1 chunks, rebuilt from the articles (spec 01 chunking) ------------------

@dataclass(frozen=True)
class KBChunk:
    chunk_id: str
    article_id: str
    heading: str
    text: str


def read_article(path: Path) -> tuple[str, str, str]:
    """(article_id, title, body after the front matter)."""
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if match is None:
        raise ValueError(f"{path.name}: no front matter")
    fields = dict(
        line.split(":", 1) for line in match.group(1).splitlines() if ":" in line
    )
    title = fields["title"].strip()
    if len(title) >= 2 and title[0] == title[-1] and title[0] in "\"'":
        title = title[1:-1]  # YAML quoted scalar
    return fields["article_id"].strip(), title, match.group(2)


def article_chunks(article_id: str, title: str, body: str) -> list[KBChunk]:
    """Spec 01: drop '# Title', split at '##' headings, prefix
    '<Title> — <Heading>', text before the first '##' is 'Overview'.
    Sections are not split further here; verify_chunks() proves that
    against the real index."""
    sections: list[tuple[str, list[str]]] = [("Overview", [])]
    for line in body.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    chunks = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        n = len(chunks) + 1
        chunks.append(
            KBChunk(f"{article_id}#c{n}", article_id, heading, f"{title}{TITLE_SEPARATOR}{heading}\n\n{text}")
        )
    return chunks


def load_kb_chunks(kb_dir: Path = KB_DIR) -> dict[str, list[KBChunk]]:
    """article_id -> its chunks in order."""
    by_article: dict[str, list[KBChunk]] = {}
    for path in sorted(kb_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        article_id, title, body = read_article(path)
        by_article[article_id] = article_chunks(article_id, title, body)
    return by_article


def verify_chunks(retriever, by_article: dict[str, list[KBChunk]], seen_texts: dict[str, str]) -> list[str]:
    """Problems found when the rebuilt chunks are compared with the real
    index (through search) and with chunk texts recorded in handoffs."""
    problems = []
    for chunks in by_article.values():
        for c in chunks:
            hits = {h.chunk_id: h.text for h in retriever.search(c.text, WIDE_K)}
            if hits.get(c.chunk_id) != c.text:
                problems.append(f"{c.chunk_id}: rebuilt text not found in the index under this id")
    flat = {c.chunk_id: c.text for chunks in by_article.values() for c in chunks}
    for chunk_id, text in seen_texts.items():
        if flat.get(chunk_id) != text:
            problems.append(f"{chunk_id}: handoff text differs from the rebuilt chunk")
    return problems


# --- Codes and numbers with units (spec 02 step 5e, decision 9) -----------------
# Written from the spec, independently of query/ (spec 05 Independence).

CODE = re.compile(r"(?<![A-Za-z0-9])([EP])[\s-]?([0-9]{1,3})(?![0-9A-Za-z])")

# Surface form -> canonical unit. Aliases per decision 9 ("tolerant of
# spacing and aliases"). V AC / V DC / VAC / VDC count as V.
UNIT_ALIASES = {
    "V": "V", "VAC": "V", "VDC": "V", "V AC": "V", "V DC": "V", "kV": "kV",
    "A": "A", "mA": "mA", "Hz": "Hz", "kHz": "kHz", "W": "W", "kW": "kW", "hp": "hp",
    "ms": "ms", "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "h": "h", "hour": "h", "hours": "h",
    "°C": "°C", "° C": "°C", "%": "%", "mm": "mm", "mm²": "mm²", "mm2": "mm²", "m": "m",
    "Nm": "Nm", "rpm": "rpm", "Ω": "Ω", "kΩ": "kΩ", "µF": "µF", "μF": "µF",
}
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(UNIT_ALIASES, key=len, reverse=True))
NUMBER_UNIT = re.compile(
    r"(?<![\w.\-−])([+\-−]?[0-9]+(?:[.,][0-9]+)?)[  \-]?(" + _UNIT_ALT + r")(?![A-Za-z0-9²])"
)


def canonical_code(letter: str, digits: str) -> str:
    return f"{letter.upper()}-{int(digits):02d}"


def canonical_number(raw: str) -> str:
    s = raw.replace("−", "-").lstrip("+")
    if re.fullmatch(r"-?[0-9]+,[0-9]{3}", s):
        s = s.replace(",", "")
    s = s.replace(",", ".")
    value = float(s)
    return f"{value:g}"


@dataclass(frozen=True)
class Item:
    surface: str  # as written in the draft
    key: str  # canonical form used for matching


def items_in(text: str) -> list[Item]:
    """Distinct codes and numbers with units, in order of appearance."""
    found: dict[str, Item] = {}
    spans = []
    for m in CODE.finditer(text):
        key = canonical_code(m.group(1), m.group(2))
        spans.append((m.start(), Item(m.group(0), key)))
    for m in NUMBER_UNIT.finditer(text):
        key = f"{canonical_number(m.group(1))} {UNIT_ALIASES[m.group(2)]}"
        spans.append((m.start(), Item(m.group(0), key)))
    for _, item in sorted(spans, key=lambda p: p[0]):
        found.setdefault(item.key, item)
    return list(found.values())


def keys_in(text: str) -> set[str]:
    return {i.key for i in items_in(text)}


# --- Retrieval replay (spec 02 step 3, through the public contract) -------------

def replay(retriever, query: str, titles_by_code: dict[str, list[str]]):
    """(merged list before diversity, final retrieved chunks).
    search() adds the BGE prefix itself (spec 03 v1.4)."""
    texts = [query] + boost_queries(query, titles_by_code)
    merged = merge(*(retriever.search(t, WIDE_K) for t in texts))
    return merged, diversify(merged)


# --- Report -------------------------------------------------------------------

def yes(flag: bool) -> str:
    return "yes" if flag else "–"


def heading_of(chunk_id: str, by_id: dict[str, KBChunk]) -> str:
    return by_id[chunk_id].heading


def diagnose(run: dict, handoffs: dict[str, dict], notes: dict[str, str], retriever) -> dict:
    by_article = load_kb_chunks()
    by_id = {c.chunk_id: c for chunks in by_article.values() for c in chunks}
    seen_texts = {
        c["chunk_id"]: c["text"] for h in handoffs.values() for c in h["retrieved_chunks"]
    }
    problems = verify_chunks(retriever, by_article, seen_texts)
    titles_by_code = code_titles(retriever.kb_info())

    tickets = run["tickets"]
    replay_mismatch = []
    merged_by_ticket = {}
    for t in tickets:
        merged, final = replay(retriever, t["question_sent"], titles_by_code)
        merged_by_ticket[t["ticket_id"]] = merged
        if [c.chunk_id for c in final] != [c["chunk_id"] for c in t["retrieved_chunks"]]:
            replay_mismatch.append(t["ticket_id"])

    # A. Grounding failures.
    part_a = []
    for t in (t for t in tickets if t["failed_check"] == "grounding"):
        cited = list(t["model_output"]["used_article_ids"])
        retrieved_ids = {c["chunk_id"] for c in t["retrieved_chunks"]}
        rows = []
        for item in items_in(t["rejected_answer"]):
            in_q = item.key in keys_in(t["question_sent"])
            in_cited_retr = any(
                item.key in keys_in(by_id[c["chunk_id"]].text)
                for c in t["retrieved_chunks"] if c["article_id"] in cited
            )
            in_other_retr = any(
                item.key in keys_in(by_id[c["chunk_id"]].text)
                for c in t["retrieved_chunks"] if c["article_id"] not in cited
            )
            in_cited_dropped = [
                c.chunk_id for a in cited for c in by_article.get(a, [])
                if c.chunk_id not in retrieved_ids and item.key in keys_in(c.text)
            ]
            elsewhere = sorted({
                c.article_id for chunks in by_article.values() for c in chunks
                if c.article_id not in cited and c.chunk_id not in retrieved_ids
                and item.key in keys_in(c.text)
            })
            number = item.key.split(" ")[0] if " " in item.key else None
            bare_in_q = number is not None and any(
                canonical_number(m) == number
                for m in re.findall(r"(?<![\w.\-])[0-9]+(?:\.[0-9]+)?", t["question_sent"])
            )
            rows.append({
                "item": item.surface, "key": item.key, "question": in_q, "bare_in_question": bare_in_q,
                "cited_retrieved": in_cited_retr, "other_retrieved": in_other_retr,
                "cited_dropped": in_cited_dropped,
                "nowhere": not (in_q or in_cited_retr or in_other_retr or in_cited_dropped),
                "elsewhere_kb": elsewhere,
            })
        part_a.append({"ticket": t, "cited": cited, "rows": rows})

    # B. insufficient_context with an expected article retrieved.
    part_b = []
    for t in tickets:
        if not (t["expected"] == "answer" and t["status"] == "escalated"
                and t["escalation_reason"] == "insufficient_context"):
            continue
        retrieved = {c["article_id"]: c for c in t["retrieved_chunks"]}
        hit = [a for a in t["expected_article_ids"] if a in retrieved]
        if not hit:
            continue
        merged = merged_by_ticket[t["ticket_id"]]
        rank_of = {c.chunk_id: (i + 1, c.similarity_score) for i, c in enumerate(merged)}
        articles = []
        for a in t["expected_article_ids"]:
            if a not in retrieved:
                articles.append({"article_id": a, "retrieved": None})
                continue
            kept = retrieved[a]["chunk_id"]
            dropped = [
                {"chunk_id": c.chunk_id, "heading": c.heading, "rank": rank_of.get(c.chunk_id)}
                for c in by_article[a] if c.chunk_id != kept
            ]
            articles.append({
                "article_id": a, "retrieved": kept, "heading": heading_of(kept, by_id),
                "rank": rank_of.get(kept), "dropped": dropped,
            })
        part_b.append({"ticket": t, "articles": articles, "notes": notes.get(t["ticket_id"], "")})

    return {"problems": problems, "replay_mismatch": replay_mismatch,
            "part_a": part_a, "part_b": part_b, "by_article": by_article}


def fmt_rank(r) -> str:
    return f"#{r[0]} ({r[1]:.4f})" if r else "not in top 20 of any search"


def render(run: dict, run_path: Path, result: dict) -> str:
    tickets = run["tickets"]
    wrong = [t for t in tickets if t["expected"] == "answer" and t["status"] == "escalated"]
    ac1 = run["summary"]["full"]["ac1"]
    n_chunks = sum(len(c) for c in result["by_article"].values())
    L = []
    w = L.append
    w("# Part B run 1: free diagnosis of the AC1 failures")
    w("")
    w("No model calls. Inputs (all read-only): "
      f"`{run_path.name}`, `{run['handoffs_file']}`, `evals/support_questions.jsonl` "
      "(notes field), `data/kb_v1/`. Retrieval was replayed through "
      "`open_retrieval('v1')`, `search()` and `kb_info()` only.")
    w("")
    w(f"- Run 1: commit `{run['git_commit'][:12]}`, model `{run['model_id']}`, "
      f"AC1 {ac1['passed']}/{ac1['total']}")
    w(f"- Wrong escalations (\"answer\" tickets escalated): {len(wrong)}")
    w("")
    w("## Checks on this diagnosis")
    w("")
    w(f"- kb_v1 chunks rebuilt from the articles with spec 01 rules: "
      f"{len(result['by_article'])} articles, {n_chunks} chunks.")
    if result["problems"]:
        w(f"- **Chunk verification FAILED** ({len(result['problems'])}):")
        for p in result["problems"]:
            w(f"  - {p}")
    else:
        w("- Every rebuilt chunk was found in the real v1 index under the same chunk_id "
          "with identical text (one `search(chunk_text, 20)` per chunk), and every chunk "
          "text recorded in the run 1 handoffs matches. No section was split.")
    if result["replay_mismatch"]:
        w(f"- **Retrieval replay differs from run 1** for: {', '.join(result['replay_mismatch'])}")
    else:
        w(f"- Retrieval replay (spec 02 step 3) reproduces run 1's final chunk ids "
          f"exactly on {len(tickets)}/{len(tickets)} tickets, so the ranks below are the run's ranks.")
    w("- Codes and numbers with units are extracted by this script, written from "
      "spec 02 (step 5e, decision 9), not by the bot's grounding check. Matching is by "
      "canonical form: codes as `E-xx`/`P-xx`; numbers as values (10.0 = 10) with unit "
      "aliases (s/sec/seconds, min/minutes, V/VAC/V DC). The bot's check may differ in "
      "detail; the run record does not say which item failed it.")
    w("")

    # A
    w("## A. Grounding failures: codes and numbers in the rejected drafts")
    w("")
    w("Columns: (a) in the question; (b) in the retrieved chunks of the cited "
      "articles (what the grounding check sees); (c) in other retrieved chunks; "
      "(d) in chunks of the cited articles that were NOT retrieved; (e) none of these. "
      "The last column lists other kb_v1 articles that contain an (e) item.")
    w("")
    for entry in result["part_a"]:
        t = entry["ticket"]
        retrieved = ", ".join(c["chunk_id"] for c in t["retrieved_chunks"])
        w(f"### {t['ticket_id']} (cited {', '.join(entry['cited'])})")
        w("")
        w(f"Question: {t['question_sent']}")
        w("")
        w(f"Retrieved: {retrieved}")
        w("")
        w("| Item | (a) question | (b) cited, retrieved | (c) other retrieved | (d) cited, not retrieved | (e) nowhere | other kb_v1 articles |")
        w("|---|---|---|---|---|---|---|")
        for r in entry["rows"]:
            w(f"| `{r['item']}` | {yes(r['question'])} | {yes(r['cited_retrieved'])} | "
              f"{yes(r['other_retrieved'])} | {', '.join(r['cited_dropped']) or '–'} | "
              f"{('**yes** (number in question, unit added)' if r['bare_in_question'] else '**yes**') if r['nowhere'] else '–'} | "
              f"{', '.join(r['elsewhere_kb']) if r['nowhere'] and r['elsewhere_kb'] else '–'} |")
        unsupported = [r for r in entry["rows"] if not r["cited_retrieved"]]
        w("")
        w(f"Items the grounding check cannot find (not in b): "
          f"{', '.join('`' + r['item'] + '`' for r in unsupported) or 'none'}")
        w("")

    # B
    w("## B. Model said insufficient_context although an expected article was retrieved")
    w("")
    w("Diversity keeps only the best chunk of each article, so the model sees ONE "
      "chunk per article. Rank = position in the merged list before diversity "
      "(main search plus code boost, k=20 each), with the chunk's score.")
    w("")
    for entry in result["part_b"]:
        t = entry["ticket"]
        tag = f", failed_check {t['failed_check']}" if t["failed_check"] else ", model decision insufficient_context"
        w(f"### {t['ticket_id']} ({t['split']}{tag})")
        w("")
        w(f"Question: {t['question_sent']}")
        w("")
        w(f"Ticket note: {entry['notes']}")
        w("")
        for a in entry["articles"]:
            if a["retrieved"] is None:
                w(f"- {a['article_id']}: **not retrieved**")
                continue
            w(f"- {a['article_id']}: kept `{a['retrieved']}` \"{a['heading']}\" at {fmt_rank(a['rank'])}")
            for d in a["dropped"]:
                w(f"  - dropped `{d['chunk_id']}` \"{d['heading']}\" at {fmt_rank(d['rank'])}")
        w("")

    # C
    w("## C. Summary: what each cause would explain")
    w("")
    w(summary(result, tickets, wrong))
    return "\n".join(L) + "\n"


SUBSTANTIVE = ("Possible causes", "Recommended actions")


def summary(result: dict, tickets: list[dict], wrong: list[dict]) -> str:
    L = []
    w = L.append
    ga = result["part_a"]
    def source(r):
        if r["question"] or r["bare_in_question"]:
            return "question"
        if r["cited_dropped"]:
            return "dropped"
        return "other_retrieved" if r["other_retrieved"] else "nowhere"

    def sources(e):
        return {source(r) for r in e["rows"] if not r["cited_retrieved"]}

    only_d = [e for e in ga if sources(e) == {"dropped"}]
    q_only = [e for e in ga if sources(e) == {"question"}]
    mixed = [e for e in ga if len(sources(e)) > 1]
    invented = [e for e in ga if sources(e) & {"nowhere", "other_retrieved"}]
    ids = lambda es: ", ".join(e["ticket"]["ticket_id"] for e in es) or "none"

    pb = [e for e in result["part_b"] if not e["ticket"]["failed_check"]]
    meaning_only = [e for e in pb if all(
        a["retrieved"] is None or a["heading"] not in SUBSTANTIVE for a in e["articles"])]
    retr_miss = [t for t in wrong if t["escalation_reason"] == "insufficient_context"
                 and not any(a in {c["article_id"] for c in t["retrieved_chunks"]} for a in t["expected_article_ids"])]
    oos = [t for t in wrong if t["escalation_reason"] == "out_of_scope"]
    tid = lambda ts: ", ".join(t["ticket_id"] for t in ts) or "none"

    answered_fail = [t["ticket_id"] for t in tickets if t["expected"] == "answer"
                     and t["status"] == "answered" and not t["ac_pass"]]
    w(f"{len(wrong)} \"answer\" tickets were escalated in run 1. AC1 also fails on "
      f"{', '.join(answered_fail) or 'none'} (answered, but not citing an expected article); "
      "not covered here.")
    w("")
    w("| Cause | Tickets | Count |")
    w("|---|---|---|")
    w(f"| 1. Grounding: every unsupported item is in a dropped chunk of a cited article (d); the check sees only ONE chunk per cited article | {ids(only_d)} | {len(only_d)} |")
    w(f"| 2. Grounding: every unsupported item is a number taken from the question (a), incl. a bare number given a unit | {ids(q_only)} | {len(q_only)} |")
    w(f"| 2b. Grounding: unsupported items from more than one of these sources | {ids(mixed)} | {len(mixed)} |")
    w(f"| 3. Grounding: an unsupported item not in the question nor in any chunk of a cited article (invented, or from a non-cited article) | {ids(invented)} | {len(invented)} |")
    w(f"| 4. Model chose insufficient_context with an expected article retrieved (B, no failed_check) | {tid([e['ticket'] for e in pb])} | {len(pb)} |")
    w(f"| 4a. of which the expected article(s) reached the model only as a chunk other than \"Possible causes\" / \"Recommended actions\" | {tid([e['ticket'] for e in meaning_only])} | {len(meaning_only)} |")
    w(f"| 5. No expected article retrieved (retrieval miss) | {tid(retr_miss)} | {len(retr_miss)} |")
    w(f"| 6. Model chose out_of_scope | {tid(oos)} | {len(oos)} |")
    w("")
    w("Grounding rows 1-3 classify each unsupported item (not in b) once: from the question "
      "if the question has it, or has its bare number (even if a dropped chunk also has it, "
      "e.g. T-005 `5 s`; T-009 `6.0 A` is the question's \"6.0\" with a unit added); "
      "else from a dropped chunk if (d); else invented.")
    w("")
    w("Cause 4a is a free proxy only: it shows which section the model saw, not "
      "whether the answer was in it. The ticket notes in section B let a human check.")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, type=Path, help="Part B run .json")
    ap.add_argument("--out", type=Path, help="report .md (default: <run>-diagnosis.md)")
    args = ap.parse_args(argv)

    run = json.loads(args.run.read_text(encoding="utf-8"))
    handoffs_path = args.run.parent / run["handoffs_file"]
    handoffs = {}
    for line in handoffs_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            handoffs[rec["handoff_id"]] = rec
    notes = {}
    for line in TICKETS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            notes[raw["ticket_id"]] = raw.get("notes", "")

    from ingestion import open_retrieval

    result = diagnose(run, handoffs, notes, open_retrieval(KB_VERSION))
    out = args.out or args.run.with_name(args.run.stem + "-diagnosis.md")
    out.write_text(render(run, args.run, result), encoding="utf-8")
    print(f"wrote {out}")
    if result["problems"] or result["replay_mismatch"]:
        print("WARNING: verification problems, see the report", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
