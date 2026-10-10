"""The pinned embedding model and its tokenizer."""

from functools import lru_cache

import numpy as np
from transformers import AutoTokenizer

from ingestion.config import MODEL_NAME, MODEL_REVISION

EMBEDDING_BATCH_SIZE = 32  # fixed, so builds are repeatable


class TokenCounter:
    """Counts tokens with the pinned model's own tokenizer."""

    def __init__(self, tokenizer):
        self._tokenizer = tokenizer

    def count(self, text: str, special_tokens: bool = True) -> int:
        """Token count of text; special_tokens adds [CLS] and [SEP]."""
        return len(
            self._tokenizer.encode(
                text, add_special_tokens=special_tokens, verbose=False
            )
        )


@lru_cache(maxsize=1)
def load_token_counter() -> TokenCounter:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION)
    return TokenCounter(tokenizer)


@lru_cache(maxsize=1)
def load_model():
    """BAAI/bge-small-en-v1.5 at the pinned revision, on CPU."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")


def embed(model, texts: list[str]) -> np.ndarray:
    """Unit-length float32 vectors, one row per text, in input order."""
    vectors = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.ascontiguousarray(vectors, dtype=np.float32)
