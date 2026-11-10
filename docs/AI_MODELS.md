# M5 model and tokenizer manifest

M5.1 has an incomplete experimental prompt/validation candidate,
`evidence-claims-3`, using the same pinned 1.5B model below. Its development-only
run did not establish useful generated answers. The application release gate
remains closed. A 3B alternative was investigated but has not been configured
or run. See [checkpoint details](M5_1_RESUME.md). The M5 manifest below is the
historical baseline.

| Component            | Pinned artifact                                                                                                         | License                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| MiniLM embeddings    | `sentence-transformers/all-MiniLM-L6-v2` at `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, upstream FP32 `onnx/model.onnx` | Apache-2.0                        |
| MiniLM tokenizer     | `tokenizer.json` from the same revision                                                                                 | Apache-2.0                        |
| Local generator      | Ollama `qwen2.5:1.5b`, Q4_K_M manifest `sha256:65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`        | Apache-2.0 for this exact variant |
| Generation tokenizer | `Qwen/Qwen2.5-1.5B-Instruct` at `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, `tokenizer.json`                            | Apache-2.0                        |
| Local runtime        | Ollama 0.40.15, optional Compose image digest `sha256:0e59999e0e8f9fd4e704bd788a89b7e4cad399367fb1365f8c102ac662288761` | MIT runtime                       |

The preparation command verifies these SHA-256 checksums before moving files
into the model directory. The worker verifies the local files again when loading.

| Local file              | SHA-256                                                            |
| ----------------------- | ------------------------------------------------------------------ |
| `minilm.onnx`           | `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452` |
| `minilm-tokenizer.json` | `be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037` |
| `qwen-tokenizer.json`   | `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539` |

Runtime labels are `policy-claims-2` for the generation prompt and
`rrf-english-1` for retrieval. The worker checks the Ollama manifest before
sending the prompt and again before accepting an answer. The adapter sets the
context to 4,096 tokens and the output cap to 600. The MiniLM runtime is CPU
only and uses two inference threads. The reference Compose resource caps are
768 MiB and two CPU cores for the AI worker and 4 GiB and three cores for the
optional Ollama service. These are configured limits. Measured evaluation
conditions and latency are recorded separately.

The application generation gate is closed. The evaluation harness can invoke
the adapter directly with the fictional corpus. A runtime flag alone cannot
enable generated answers in the application.

Upstream references include the embedding model card, the exact generation
artifact and license listing, the tokenizer repository, and the Ollama runtime
license. [MiniLM model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41) ·
[Ollama Qwen artifact](https://ollama.com/library/qwen2.5:1.5b) ·
[Qwen tokenizer](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/tree/989aa7980e4cf806f80c7fef2b1adb7bc71aa306) ·
[Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.15) ·
[Ollama license](https://github.com/ollama/ollama/blob/v0.40.15/LICENSE)
