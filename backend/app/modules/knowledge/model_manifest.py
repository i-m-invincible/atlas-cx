"""Exact public artifacts used by the offline preparation command and AI worker."""

from dataclasses import dataclass
from pathlib import Path

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
GENERATION_MODEL = "qwen2.5:1.5b"
GENERATION_DIGEST = "sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b"
GENERATION_TOKENIZER = "Qwen/Qwen2.5-1.5B-Instruct"
GENERATION_TOKENIZER_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
PROMPT_VERSION = "policy-claims-2"
# A measured release decision. Evaluation may invoke the pinned adapter directly.
GENERATION_RELEASE_APPROVED = False


@dataclass(frozen=True)
class Artifact:
    repository: str
    revision: str
    upstream_path: str
    name: str
    sha256: str

    @property
    def url(self) -> str:
        return (
            f"https://huggingface.co/{self.repository}/resolve/{self.revision}/{self.upstream_path}"
        )

    def verify(self, directory: Path) -> Path:
        import hashlib

        path = directory / self.name
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != self.sha256:
                raise ValueError("Model artifact checksum mismatch")
        return path


MINILM_TOKENIZER = Artifact(
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    "tokenizer.json",
    "minilm-tokenizer.json",
    "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
)
MINILM_ONNX = Artifact(
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    "onnx/model.onnx",
    "minilm.onnx",
    "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
)
QWEN_TOKENIZER = Artifact(
    GENERATION_TOKENIZER,
    GENERATION_TOKENIZER_REVISION,
    "tokenizer.json",
    "qwen-tokenizer.json",
    "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539",
)
ARTIFACTS = (MINILM_TOKENIZER, MINILM_ONNX, QWEN_TOKENIZER)
