"""Evaluation-only comparison. The application never selects this research model."""

from app.modules.knowledge.providers import Ollama


class ResearchQwen3B(Ollama):
    model = "qwen2.5:3b"
    digest = "sha256:357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b"

    # Official tokenizer at aa8e72537993ba99e69dfaafa59ed015b17504d1 was
    # verified byte-identical to the existing pinned Qwen tokenizer. This
    # Q4_K_M artifact has the Qwen research license, not Apache-2.0.
