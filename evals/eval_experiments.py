"""Part A2: retrieval experiments (spec 05). No model calls.

Each experiment is simulated through the public retrieval contract only
(search and kb_info); query/ is not changed. Every experiment starts
from the flow's own masked and normalised query (recorded by Part A).
"""

import re
from collections.abc import Callable

from evals.eval_scoring import counts_for_both_cited, rate_of
from evals.eval_tickets import SETS, Ticket, select
from ingestion import Chunk, KBInfo

FINAL_K = 5  # chunks the flow gives the model (spec 02 step 3)
WIDE_K = 20  # E2: search wide, then diversify (spec 03 allows k up to 20)
MAX_ARTICLES = 5

# E1: the query instruction published with BAAI/bge-small-en-v1.5 for
# short-query-to-passage retrieval. Passages are embedded without it.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# A fault code after spec 02 normalisation: "E-" and 2-3 digits.
FAULT_CODE = re.compile(r"(?<![A-Za-z0-9])E-[0-9]{2,3}(?![A-Za-z0-9])")

BASELINE = "baseline"
EXPERIMENTS = (BASELINE, "E1", "E2", "E3", "E2+E3", "E1+E3", "E1+E2+E3")
DESCRIPTIONS = {
    BASELINE: "the flow as it is: search(query, k=5)",
    "E1": "BGE query prefix: search(prefix + query, k=5)",
    "E2": "diversity: search(query, k=20), best chunk of each of up to 5 articles",
    "E3": "code boost: also search each known E-xx code's article title (k=5); merge, top 5 by score",
    "E2+E3": "code boost at k=20, merged, then diversity to up to 5 articles",
    "E1+E3": "code boost with the prefix on every search (question and titles), k=5; merge, top 5 by score",
    "E1+E2+E3": "code boost with the prefix on every search, k=20, merged, then diversity to up to 5 articles",
}


def fault_codes_in(text: str) -> list[str]:
    """Distinct E-xx codes in order of appearance."""
    return list(dict.fromkeys(FAULT_CODE.findall(text)))


def code_titles(info: KBInfo) -> dict[str, list[str]]:
    """Known fault code -> titles of the articles whose title names it."""
    titles: dict[str, list[str]] = {}
    for _article_id, title in info.articles:
        for code in fault_codes_in(title):
            titles.setdefault(code, []).append(title)
    return titles


def boost_queries(query: str, titles_by_code: dict[str, list[str]]) -> list[str]:
    """E3: the titles to search for the known codes in the query."""
    return [title for code in fault_codes_in(query) for title in titles_by_code.get(code, [])]


def rank(chunks) -> list[Chunk]:
    """Spec 03 order: score descending, ties by chunk_id."""
    return sorted(chunks, key=lambda c: (-c.similarity_score, c.chunk_id))


def merge(*results: list[Chunk]) -> list[Chunk]:
    """Union by chunk_id; a chunk found twice keeps its higher score."""
    best: dict[str, Chunk] = {}
    for chunks in results:
        for c in chunks:
            if c.chunk_id not in best or c.similarity_score > best[c.chunk_id].similarity_score:
                best[c.chunk_id] = c
    return rank(best.values())


def diversify(chunks: list[Chunk], max_articles: int = MAX_ARTICLES) -> list[Chunk]:
    """The best chunk of each article, for up to max_articles articles."""
    picked: list[Chunk] = []
    seen: set[str] = set()
    for c in rank(chunks):
        if c.article_id not in seen:
            seen.add(c.article_id)
            picked.append(c)
            if len(picked) == max_articles:
                break
    return picked


def experiment_parts(name: str) -> frozenset[str]:
    if name not in EXPERIMENTS:
        raise ValueError(f"unknown experiment {name!r}")
    return frozenset() if name == BASELINE else frozenset(name.split("+"))


def run_experiment(name: str, retriever, query: str, titles_by_code: dict[str, list[str]]) -> list[Chunk]:
    """E1 adds the prefix to every search, E2 searches wide then
    diversifies, E3 adds a title search per known code in the query."""
    parts = experiment_parts(name)
    search: Callable[[str, int], list[Chunk]] = retriever.search
    prefix = BGE_QUERY_PREFIX if "E1" in parts else ""
    k = WIDE_K if "E2" in parts else FINAL_K
    # Codes are found in the flow's query, never in the prefix.
    texts = [query] + (boost_queries(query, titles_by_code) if "E3" in parts else [])
    merged = merge(*(search(prefix + text, k) for text in texts))
    return diversify(merged) if "E2" in parts else merged[:FINAL_K]


# --- Comparison with the baseline ------------------------------------------------


def improves(result: dict, baseline: dict) -> bool:
    """Summary rule shown in the report: more recall hits, and no fewer
    both-articles hits, than the baseline on the same set."""
    return (
        result["recall"]["passed"] > baseline["recall"]["passed"]
        and result["both_recall"]["passed"] >= baseline["both_recall"]["passed"]
    )


def experiment_summary(tickets: list[Ticket], rows: dict[str, dict]) -> dict:
    """Per set and experiment: recall, both-articles recall, and the
    tickets gained or lost against the baseline. rows[ticket_id]
    ["results"][experiment] holds recall_hit and both_hit."""
    summary: dict = {}
    for set_name in SETS:
        answer = [t for t in select(tickets, set_name) if t.expected == "answer"]

        def hit(t: Ticket, name: str) -> bool:
            return rows[t.ticket_id]["results"][name]["recall_hit"]

        per_experiment = {}
        for name in EXPERIMENTS:
            per_experiment[name] = {
                "recall": rate_of(hit(t, name) for t in answer).to_dict(),
                "both_recall": rate_of(
                    rows[t.ticket_id]["results"][name]["both_hit"] for t in answer if counts_for_both_cited(t)
                ).to_dict(),
                "any_match_tickets": [
                    {"ticket_id": t.ticket_id, "recall_hit": hit(t, name)} for t in answer if t.article_match == "any"
                ],
                "gained": [t.ticket_id for t in answer if hit(t, name) and not hit(t, BASELINE)],
                "lost": [t.ticket_id for t in answer if hit(t, BASELINE) and not hit(t, name)],
            }
        base = per_experiment[BASELINE]
        for name in EXPERIMENTS:
            r = per_experiment[name]
            r["recall_change"] = r["recall"]["passed"] - base["recall"]["passed"]
            r["both_recall_change"] = r["both_recall"]["passed"] - base["both_recall"]["passed"]
            r["improves_on_baseline"] = name != BASELINE and improves(r, base)
        summary[set_name] = per_experiment
    return summary
