"""Retrieval (spec 02, Processing step 3; experiments E2 and E3 of
spec 05, adopted at Step 9).

a. Main search: search(query, k=SEARCH_K).
b. Code boost: for every known E-xx code in the normalised question,
   also search(<that article's title from kb_info()>, k=SEARCH_K).
c. Merge: each chunk once, at its highest score, sorted as spec 03 says
   (score descending, ties by chunk_id ascending).
d. Diversity: the best chunk of each article, up to MAX_ARTICLES
   articles. These are the retrieved chunks: the retrieval check, the
   citation check, the citations and the handoff record use them.
e. Reading (spec 02 v1.14): the model is given ALL chunks of the
   selected articles (article_chunks(), spec 03 v1.5), in article order
   and chunk order. Steps a-d choose WHICH articles; step e decides WHAT
   the model reads. The grounding check and the safety warnings use
   these read chunks.

search() adds the query prefix itself (spec 03); it is never added here.
"""

from collections.abc import Mapping
from typing import Protocol

from ingestion import Chunk
from query.config import MAX_ARTICLES, SEARCH_K
from query.fault_codes import fault_codes_in


class Searcher(Protocol):
    def search(self, query: str, k: int) -> list[Chunk]: ...


class ArticleReader(Protocol):
    def article_chunks(self, article_id: str) -> list[Chunk]: ...


def contract_order(chunk: Chunk) -> tuple[float, str]:
    """Spec 03 ordering: highest score first, equal scores by chunk_id."""
    return (-chunk.similarity_score, chunk.chunk_id)


def merge(*result_lists: list[Chunk]) -> list[Chunk]:
    """Every chunk once, at its highest score, in spec 03 order (step 3c)."""
    best: dict[str, Chunk] = {}
    for results in result_lists:
        for chunk in results:
            kept = best.get(chunk.chunk_id)
            if kept is None or chunk.similarity_score > kept.similarity_score:
                best[chunk.chunk_id] = chunk
    return sorted(best.values(), key=contract_order)


def diversify(chunks: list[Chunk], max_articles: int = MAX_ARTICLES) -> list[Chunk]:
    """The best chunk of each article, up to max_articles articles (step 3d).

    chunks must already be in spec 03 order (as merge() returns them), so
    the first chunk seen for an article is its best.
    """
    kept: dict[str, Chunk] = {}
    for chunk in chunks:
        if len(kept) == max_articles:
            break
        kept.setdefault(chunk.article_id, chunk)
    return list(kept.values())


def boost_titles(normalised_question: str, code_titles: Mapping[str, str]) -> list[str]:
    """Titles to search for the code boost (step 3b): one per KNOWN E-xx
    code in the question, in order of appearance, without repeats.
    Unknown codes and P-xx codes are not boosted."""
    return [code_titles[c] for c in fault_codes_in(normalised_question) if c in code_titles]


def retrieve(
    retriever: Searcher,
    normalised_question: str,
    code_titles: Mapping[str, str],
) -> list[Chunk]:
    """The retrieved chunks for one masked, normalised question (step 3)."""
    results = [retriever.search(normalised_question, k=SEARCH_K)]
    results += [retriever.search(title, k=SEARCH_K) for title in boost_titles(normalised_question, code_titles)]
    return diversify(merge(*results), MAX_ARTICLES)


def read_articles(retriever: ArticleReader, retrieved: list[Chunk]) -> list[Chunk]:
    """What the model reads (step 3e): every chunk of each retrieved
    article, articles in the order of the retrieved chunks (step d),
    chunks in the order article_chunks() returns them (c1, c2, ...)."""
    articles = dict.fromkeys(c.article_id for c in retrieved)
    return [chunk for article_id in articles for chunk in retriever.article_chunks(article_id)]
