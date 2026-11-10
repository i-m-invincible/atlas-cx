# M5 model and tokenizer manifest

M5.1 selected and froze `evidence-claims-5` on the same pinned 1.5B model below.
The freeze record is `backend/evaluation/m51-frozen-candidate.json`. It improves
development usefulness but fails unanswerable abstention. The application
release gate remains closed. `policy-claims-2` is the historical M5 baseline;
`evidence-claims-3` generated no usable development answers. See RAG_EVALUATION.md
for the development comparison and prospective confirmation evidence.

The evaluation-only 3B comparison is Ollama `qwen2.5:3b` Q4_K_M, manifest
`sha256:357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
The model layer is 1,929,903,008 bytes. Its tokenizer at
`Qwen/Qwen2.5-3B-Instruct` revision `aa8e72537993ba99e69dfaafa59ed015b17504d1`
was verified byte-identical to the existing Qwen tokenizer checksum below.
It uses the Qwen research license, restricted to research/evaluation. It is
not selected by the application. Comparison runs impose a 4 GiB memory limit
and three-core CPU quota on the private Ollama service, with one loaded model.
No paid provider is used. Actual costs are token counts and measured runtime,
not a claim of free hosted infrastructure. [Official artifact](https://ollama.com/library/qwen2.5:3b) ·
[Exact model repository](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/tree/aa8e72537993ba99e69dfaafa59ed015b17504d1)

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

Historical M5 labels are `policy-claims-2` for the generation prompt and
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

M5.1 keeps the 600-token output cap, split into 450 draft and 150 critique
tokens, under one 60-second deadline. Actual tokens include rejected calls.
All development comparisons use the same dataset, temperature zero, seed 42,
three inference threads and pinned Ollama 0.40.15. The native Linux archive
SHA-256 is `628c018404a4206493efd38e46251c154ede5141b8b8dc85c659b3b027c47379`.

| Development trial | Calls | Input / output tokens | Generation p50 / p95 | Service peak bytes |
| ----------------- | ----: | --------------------: | -------------------: | -----------------: |
| v4 1.5B           |    71 |        49,882 / 5,326 |      14.11 / 20.31 s |      2,376,679,424 |
| v4 3B             |    39 |          30,295 / 626 |       7.99 / 29.01 s |      4,291,489,792 |
| v5 1.5B           |    71 |        48,260 / 5,118 |       6.55 / 10.81 s |      2,361,217,024 |
| v5 3B             |    39 |          29,120 / 647 |       8.12 / 28.43 s |      4,290,621,440 |

These are single-run observations, not controlled speed benchmarks. v5 1.5B
ran on an AMD EPYC 9V45 host; the other trials used EPYC 7763 hosts. CPU quota
was identical, but hardware differs. Service MemoryPeak includes download/cache
activity and is not model-only resident memory. The 3B model approached its
4 GiB limit and generated only one incomplete answer in each run. It is not
selected for either application use or final confirmation. No provider fees
were incurred; local CPU usage and hosted runner costs are not asserted free.

Final frozen confirmation used the same EPYC 7763 host class and service caps
for both profiles. Historical M5 and candidate share the exact 1.5B artifact;
only the prompt/validation pipeline differs. No additional model was introduced.

| Final evaluation         | Calls | Input / output tokens | Generation p50 / p95 |
| ------------------------ | ----: | --------------------: | -------------------: |
| M5 baseline, new 40      |    40 |        14,443 / 3,595 |       7.79 / 10.14 s |
| v5, original held-out 20 |    36 |        25,064 / 3,357 |      15.26 / 31.18 s |
| v5, new 40               |    72 |        54,368 / 6,077 |      15.34 / 23.32 s |

The baseline service peaked at 2,728,386,560 bytes and used 924.48 CPU seconds.
The candidate service, including both held-out and confirmation runs, peaked
at 2,408,308,736 bytes and used 2,808.35 CPU seconds. These cgroup measurements
include setup/cache activity; they are not per-request costs. Both stayed within
the configured 4 GiB service limit. The second critique roughly doubles observed
confirmation latency without fixing answerability. Full counters and provenance
are in `backend/evaluation/results/m51-inference-resources.json`.

Upstream references include the embedding model card, the exact generation
artifact and license listing, the tokenizer repository, and the Ollama runtime
license. [MiniLM model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41) ·
[Ollama Qwen artifact](https://ollama.com/library/qwen2.5:1.5b) ·
[Qwen tokenizer](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/tree/989aa7980e4cf806f80c7fef2b1adb7bc71aa306) ·
[Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.15) ·
[Ollama license](https://github.com/ollama/ollama/blob/v0.40.15/LICENSE)
