# Ingestion Spec — Voltrix VX-200 Support Bot

Status: Version 1.3, approved by Shailesh on 2026-10-10

## Goal
Turn the knowledge base (Markdown articles in data/kb_v1/ or
data/kb_v2/) into a searchable vector index.
Ingestion runs on demand or on a trigger (e.g. a new KB version).
It NEVER runs in the request path a user waits on.

## Input
- Folder: given as a parameter (data/kb_v1 or data/kb_v2).
- Only *.md files directly in the folder are read; subfolders are
  not read and other files are ignored.
- README.md is EXCLUDED by name (it is not a help article).
- Files are processed in sorted filename order (byte order).
- Files are UTF-8. Text is normalised to Unicode NFC and "\n" line
  endings.
- The header block is parsed as real YAML.
- Required header fields: article_id, title, category, kb_version.
  - category must be one of: fault, installation, parameters,
    maintenance, safety.
  - kb_version must match the folder (v1 in kb_v1, v2 in kb_v2).
- Any other .md file without a valid header block (as defined
  above) makes ingestion FAIL loudly (no silent skipping).
- "Fail loudly" means: non-zero exit code, a clear message naming
  the file, and no partial output left behind.
- A folder with no articles (after excluding README.md) makes
  ingestion fail loudly.
- Extra header fields beyond the four required ones are allowed
  and ignored.
- Duplicate keys in a header block (e.g. two "title:" lines) make
  ingestion fail loudly.
- A UTF-8 byte-order mark at the start of a file is removed during
  normalisation, like CRLF line endings.

## Constraints (stated explicitly, not library defaults)
- Embedding model: BAAI/bge-small-en-v1.5, run locally with
  sentence-transformers.
  - Pinned: exact model revision (commit hash) and exact
    library versions are recorded in requirements.txt and in
    the index manifest. Filled in at Step 7.
  - Model token limit: 512 tokens.
  - Changing the model requires a spec change and a full rebuild.
- Chunking strategy:
  - Split each article at its "##" headings; each section is a chunk.
  - "###" headings belong to their parent "##" section.
  - The "# Title" line is dropped. Any other text between the title
    line and the first "##" heading is kept as its own chunk.
    Whitespace-only text there is not a chunk.
  - Chunk text starts with "<Title> — <Section heading>", so it
    makes sense alone. This prefix counts toward the 300-token limit.
    The chunk for text before the first "##" uses the prefix
    "<Title> — Overview".
  - Markdown formatting (backticks, bold) is kept as written.
  - If a section is longer than the maximum, split it further.
    - Split only at paragraph or list-item boundaries, never
      mid-sentence.
    - Each piece repeats the prefix.
    - Never split inside a Markdown table. If a table alone exceeds
      300 tokens, ingestion fails loudly.
- Maximum chunk size: 300 tokens (counted with the model's own
  tokenizer, including special tokens).
- Overlap when a section is split: 50 tokens maximum (not an exact
  size). Overlap counts toward the 300-token limit.
  - The next piece starts by repeating whole paragraphs or list
    items from the end of the previous piece, as many as fit within
    50 tokens.
  - If the last paragraph is longer than 50 tokens, repeat its last
    whole sentences that fit within 50 tokens.
  - If even the last sentence is longer than 50 tokens, use no
    overlap for that split.
- Chunk ID format: <article_id>#c<number>, e.g. KB-001#c1.
  Chunk numbers run straight through each article starting at 1,
  including pieces of a split section: KB-001#c1, KB-001#c2, ...
- If a single paragraph or list item is longer than 300 tokens,
  ingestion fails loudly (same as an oversized table).
- A "##" heading with no body text makes ingestion fail loudly.
- Duplicate article_id within a folder makes ingestion fail loudly.

## Output
- Output folder: indexes/<kb_version>/.
- A vector index file plus a chunk metadata file.
- Vectors are normalised; similarity is cosine.
- Metadata is JSONL, one chunk per line, sorted by chunk_id.
- Each chunk record carries: chunk_id, article_id, title, category,
  kb_version, text.
- A manifest file recording: KB version, model name and revision,
  chunk size, overlap, number of articles, number of chunks,
  SHA-256 hash of the index and metadata files.
- The manifest contains no timestamps.
- Index files are generated, never committed to Git.

## Acceptance criteria
1. Every source article produces at least one chunk.
   (No silent drops: number of articles in = number of articles
   represented in the index.) Articles = *.md files in the folder
   excluding README.md.
2. No chunk exceeds the embedding model's token limit (512), and no
   chunk exceeds the chosen maximum (300).
3. Every chunk carries a valid article_id from its source article.
   A valid article_id matches KB-<3 digits> and is unique.
4. README.md never appears in the index. Any other .md file without
   a valid header block makes ingestion fail loudly; it is never
   silently skipped. Tested with a deliberately broken file in
   tests/fixtures/.
5. Idempotence: running ingestion twice on the same unchanged KB
   produces byte-identical index, metadata and manifest files
   (checked by comparing SHA-256 hashes).
6. Chunk IDs are unique and numbered c1..cn with no gaps per article.
7. Manifest counts match the actual number of articles and chunks.
8. The split-and-overlap rule is tested with a synthetic long
   article in tests/fixtures/.

## Out of scope for ingestion
- Answering questions, retrieval ranking, escalation (query side).
