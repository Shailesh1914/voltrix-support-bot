# Retrieval Contract — Voltrix VX-200 Support Bot

Status: Version 1.0, approved by Shailesh on 2026-10-07

## Purpose
This contract is the ONLY interface between the ingestion side and
the query side.
- The query flow never reads index, metadata or manifest files
  directly, and never reads the knowledge base articles.
- The ingestion side never knows how its output is used.
- If ingestion changes its chunking strategy, the query flow does
  not change, as long as this contract holds.

## Ownership
The ingestion side implements this contract (in ingestion/), because
it owns the index format. The query side only calls it.

## Opening retrieval

open_retrieval(kb_version: str) -> Retriever

- The query flow opens retrieval once, passing kb_version from the
  query side's ACTIVE_KB_VERSION setting.
- Ingestion code never reads query configuration; the KB version is
  always passed in.
- The startup checks (below) run inside open_retrieval().
- The returned Retriever provides search() and kb_info().

## Function 1: search

search(query: str, k: int) -> List[Chunk]

Input:
- query: non-empty text. Used exactly as given; any normalisation
  (e.g. fault codes) is done by the query flow BEFORE calling search.
- k: integer from 1 to 20.
- Empty query or k outside 1..20 -> raises an error.

Behaviour:
- Embeds the query with the SAME pinned embedding model used for
  ingestion.
- Query instruction prefix: no prefix (Version 1.0). To be confirmed
  by experiment at Step 9: compare retrieval with and without the
  BGE retrieval prefix on the eval tickets, BEFORE the escalation
  threshold is calibrated. If the prefix is chosen, its exact text
  is written into this contract.
- Searches the index of the kb_version passed to open_retrieval()
  only.
- Caps every similarity_score to the range -1.0 to 1.0.
- Returns at most k chunks (fewer only if the index has fewer).

Output: a list of Chunk, each with:
- chunk_id (str), e.g. "KB-007#c2"
- article_id (str), e.g. "KB-007"
- title (str): the article title
- text (str): the chunk text, exactly as stored by ingestion
- kb_version (str): "v1" or "v2"
- similarity_score (float): cosine similarity between query and
  chunk, range -1.0 to 1.0, higher = more similar

Ordering:
- Sorted by similarity_score, highest first.
- Equal scores are ordered by chunk_id (ascending).
- The same query on the same index always returns the same result
  in the same order, within one run and across process restarts.

## Function 2: kb_info

kb_info() -> KBInfo

Output:
- kb_version (str)
- articles: list of (article_id, title), sorted by article_id

Used by the query flow to build the set of known fault codes.
Read-only. No other metadata is exposed.

## Startup checks (fail loudly)
open_retrieval(kb_version) must stop with a clear error (non-zero
exit or exception) if:
- the index for the requested kb_version does not exist, or
- the kb_version in the index manifest differs from the requested
  kb_version, or
- the SHA-256 hashes in the manifest do not match the index and
  metadata files, or
- the embedding model name or revision in the index manifest differs
  from the model used by search.

## Contract tests (structural, must pass 100%)
1. Every returned chunk has all six fields with the correct types.
2. Results are sorted by score descending, ties by chunk_id.
3. At most k chunks are returned.
4. Every similarity_score is between -1.0 and 1.0.
5. The same query twice on the same index returns identical
   results, within one run AND across process restarts.
6. Every returned kb_version equals the kb_version passed to
   open_retrieval().
7. Invalid input (empty query, k=0, k=21) raises an error.
8. A model mismatch with the manifest fails at startup.
9. kb_info() returns every article in the index, sorted by
   article_id.
10. A missing index for the requested kb_version fails at startup.
11. A manifest kb_version different from the requested kb_version
    fails at startup.
12. A manifest SHA-256 hash that does not match the index or
    metadata file fails at startup.
