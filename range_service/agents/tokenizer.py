"""Token counting for context budgets (CONTEXT_MEMORY_STRATEGY §4.1).

G3a has no model, so counts are an **estimate**: one token per 3.5 characters, rounded up. That
is a little more than English text usually needs (about 4 characters per token), so budgets
err on the safe side. Every log names the tokenizer (``approx_chars_v1``) so estimated counts are
never mistaken for measured ones. G3b replaces it with the model's own tokenizer (llama-server's
``/tokenize``) and re-checks every budget.
"""

from __future__ import annotations

import math
from typing import Protocol


class Tokenizer(Protocol):
    name: str

    def count(self, text: str) -> int: ...


class ApproxTokenizer:
    name = "approx_chars_v1"
    CHARS_PER_TOKEN = 3.5

    def count(self, text: str) -> int:
        return math.ceil(len(text) / self.CHARS_PER_TOKEN) if text else 0
