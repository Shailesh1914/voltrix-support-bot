"""The pinned embedding model's tokenizer (and, from stage c, the model)."""

from functools import lru_cache

from transformers import AutoTokenizer

from ingestion.config import MODEL_NAME, MODEL_REVISION


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
