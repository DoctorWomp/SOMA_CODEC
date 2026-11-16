# Quantization options for RANGE models

**Status:** research note (2026-11-16), backing the proposed decision [D-55](DECISIONS.md). **Nothing here was downloaded, run or measured in this project.** All figures are published numbers from the sources listed at the end, measured on other machines, and they are estimates for ours. The G3b bake-off on the owner's PC replaces them with measurements.
**Related:** D-20 (model shortlist and bake-off), D-21 (llama.cpp engine), D-50 (gateway, focal deadline 4 s), [INFERENCE_STRATEGY.md](INFERENCE_STRATEGY.md) (T8 KV quantization, T17 speculative decoding, T19 stepped mode), [G3_PLAN.md](gates/G3_PLAN.md) G3b

## 1. What quantization changes for us

Quantization stores each weight in fewer bits: 16 → 8 → ~4.5 (Q4_K_M) → ~3.5 (IQ3). The file shrinks, and because generation reads every active weight for each token, **generation speeds up roughly in proportion**. The cost is a small drift from the original model's answers, which grows quickly below about 4 bits.

Our workload differs from chat benchmarks:

| Our workload | Consequence |
|---|---|
| Short outputs (~50–150 tokens), focal deadline 4 s (D-50) | Generation speed matters: at 30 tokens/s a 120-token answer takes 4 s alone; at 80 tokens/s it takes 1.5 s |
| Prompts of 2–6K tokens with a stable prefix (INFERENCE_STRATEGY T3) | Prefix caching hides most prompt processing; only the new tail is processed |
| JSON-schema-constrained output (D-21) | Quantization **cannot break the format**. Its damage shows up as worse *decisions*: a wrong action, a forgotten promise, a rule ignored. **The bake-off must score decisions, not just JSON validity** |
| One 16 GB GPU shared by Godot (~1–2 GB), the focal model, the NPC model and their caches | Every GB saved is room for another slot or a longer context, and less need to cut context |
| Paired A/B trials (D-20) | The quantization is part of the model's identity: both arms must load the same file |

**Rule of thumb for speed:**

> generation tokens/s ≲ GPU memory bandwidth ÷ bytes read per token

Bytes per token is the whole file for a dense model, and only the active experts for a mixture-of-experts (MoE) model. Real speed lands at about 60–80% of that ceiling.

Check against a published figure: a 4080 (~717 GB/s) running an 11.3 GB dense 27B has a ceiling of ~63 tokens/s; it measured 45 tokens/s (71%). The owner's 4070 Ti Super has slightly lower bandwidth (~672 GB/s), so expect slightly lower speeds than published 4080 numbers.

## 2. What the evidence says about quality

| Finding | Source |
|---|---|
| On Qwen3.5-35B-A3B, mean KL divergence from the original (lower is better): Q8 0.0026 · Q6 0.0041 · Q5 0.0069 · Q4_K_XL 0.0137 · Q4_K_M 0.0192 · Q3_K_XL 0.0308 · IQ3_XXS 0.0501 · Q2_K_XL 0.097 · IQ2_XXS 0.185. **Quality drops sharply below ~3 bits**; 3-bit is "a good compromise" for the expert layers only, while the attention layers are sensitive | Unsloth Qwen3.5 GGUF benchmarks (vendor-reported) |
| Same model: Q4_K_XL (19.2 GB) has lower drift than MXFP4 (18.2 GB); Q4_K is preferred over MXFP4 | Unsloth |
| KL divergence and perplexity are only proxies: a 2-bit quant once beat a larger 3-bit one on real benchmarks. **Test on our own task** | Unsloth; community discussion |
| **Small models are the most fragile at 4 bits**; ~70B models barely notice. Quantized models struggle more with instruction following | Lee et al., IJCAI 2025 (arXiv 2409.11055) |
| Qwen3-1.7B at 4 bits nearly tripled missed tool calls (6.0% → 17.3%); Qwen3-4B showed no effect. "Validate per checkpoint" | Roshaan et al., NeurIPS 2026 listing |
| **Quantization-aware training (QAT)**: the model is trained to be good *at* 4 bits, so it keeps near-original quality there. Google publishes official QAT Q4_0 checkpoints, including GGUF, for **all five Gemma 4 sizes** | Google Gemma docs; Unsloth Gemma 4 QAT page |
| Converting QAT weights to llama.cpp Q4_0 the naive way loses accuracy (scale-format mismatch). Unsloth reports 70.2% vs 85.6% top-1 agreement on 26B-A4B with their fixed conversion. **Use the official QAT GGUF or a conversion that keeps the QAT grid** | Unsloth Gemma 4 QAT page |
| KV cache at q8_0: under ~0.1% perplexity cost and half the cache memory. At q4_0 the cost is larger and model-dependent (V suffers more than K); a quantized V cache needs flash attention. Results changed with a llama.cpp change of 2026-04-01, so only compare runs on the same build | Blog and issue reports (secondhand) |

## 3. Using larger models on one 16 GB card

There are three ways to do it.

### a) Mixture-of-experts with experts in system RAM

This is the most promising route. An MoE model has many parameters but uses only a few billion per token.

- **The models:**
  - Gemma 4 26B A4B: 26B total, 4B active; official QAT GGUF ~14.4 GB.
  - Qwen3.5- or Qwen3.6-35B-A3B: 35B total, 3B active; UD-Q4_K_XL 19.2 GB, IQ3 ~13 GB.
- **Published speeds:** on a 16 GB 4080 with the whole model on the GPU, these ran at **~120–150 tokens/s**. That's faster than a dense 9B, with far more knowledge.
- **The catch:** a whole-GPU run leaves no room for Godot and the NPC model. llama.cpp can keep some expert layers in system RAM (`--n-cpu-moe N`, or the newer `--fit`). The owner's 96 GB of RAM has room to spare, but RAM is roughly a tenth as fast as the GPU, so generation slows as more experts move out.
- **Prompt processing:** for long prompts llama.cpp copies the experts it needs to the GPU, so prompt processing usually stays fast.
- **Published example:** ~40 tokens/s at 100K context on a 16 GB card with 24 layers' experts on the CPU.
- **Risk for us:** CPU contention with Godot and Python. T25 (no frame over 50 ms) must still pass.

### b) Dense 27B–31B at ~3 bits

Qwen3.5/3.6-27B at IQ3_XXS is ~11.5 GB and ran at ~45 tokens/s at 19K context, dropping to ~23 at 64K. Gemma 4 31B at IQ3_XXS ran at ~29 tokens/s, and its QAT Q4 needs 17.5 GB, which doesn't fit.

These fill the card and are slow for live play. They do suit **stepped runs** (T19, D-48), where the world waits for answers. That makes them a "big model" **reference arm** for research questions such as D-20's "does a smaller model with HORIZON match a larger one without it?". They are not for live runs.

### c) Spending the savings on the right thing

A QAT Q4 model leaves VRAM for more slots and a longer context, so less context needs cutting, which is often worth more to an agent than an extra bit per weight.

### Speculative decoding

Google ships small "drafter" models next to the Gemma 4 QAT checkpoints, and Qwen3.6 supports multi-token prediction. Both speed up generation without changing the output. The gain is small for short outputs, so measure it (T17).

**Not for now:**
- FP8 and NVFP4 formats: NVFP4 needs a Blackwell GPU (RTX 50 series), and the 4070 Ti Super is Ada. We stay on GGUF in llama.cpp (D-21).
- Anything at 2 bits for an agent's thinking.

## 4. Proposed bake-off matrix (G3b)

**Owner direction (2026-11-16):** start with **4B–12B models**, prefer QAT where it is offered, and use smaller models for background NPCs. Bigger MoE and dense models wait until the 4B–12B results are in.

Sizes are published figures where a source gave one, otherwise estimates marked ~. The owner confirms every download (D-20, D-21), and licenses are checked on each model card first. **Files the owner already has** (for example from LM Studio) can be registered by path and SHA-256 instead of downloaded again.

### Core set (G3b)

| ID | Role | Model | File | Approx. size | Why |
|---|---|---|---|---|---|
| F1 | Robot R | Qwen3.5-9B | UD-Q4_K_XL or Q4_K_M | ~6 GB | Baseline from D-20 |
| F2 | Robot R | Qwen3.5-9B | Q6_K | ~7.5 GB | Same model, more bits: **measures what 4-bit costs us** |
| F3 | Robot R | Gemma 4 12B | official QAT Q4_0 GGUF | 6.7 GB in memory (Google, weights + 20%) | QAT at the top of the size range |
| N1 | Active NPCs (C2) | Gemma 4 E4B | official QAT Q4_0 GGUF | 4.5 GB in memory (Google) | QAT where small models are most fragile |
| N2 | Active NPCs (C2) | Qwen3.5-4B | Q6_K | ~3.5 GB | High-precision control |
| N3 | Active NPCs (C2) | Qwen3.5-4B | Q4_K_M | ~2.7 GB | **Measures small-model fragility** directly against N2 |
| S1 | Reactive NPCs (C1) | Gemma 4 E2B | official QAT Q4_0 GGUF | 2.9 GB in memory (Google) | Short lines; also tried on the CPU (T16) |
| S2 | Reactive NPCs (C1) | Qwen3.5-2B | Q6_K | ~1.8 GB | Same; kept at 6-bit because 2B models are the most fragile |

Disk for the core set: **about 35–40 GB**.

Background crowd (C0) uses **no model at all** (D-08, D-20): scripted routines only. "Smaller models for background NPCs" means the C1 reactive tier: staff answering a question, a guard.

**Does it fit on 16 GB?** In Option C (INFERENCE_STRATEGY §4), the largest pairing adds up as follows. Every figure here is to be measured.

| Item | Size |
|---|---|
| Gemma 4 12B QAT (Robot R) | 6.7 GB |
| Gemma 4 E4B QAT (NPCs) | 4.5 GB |
| Context caches | ~1.5–2 GB at f16, about half at q8_0 |
| Godot | ~1–2 GB |
| **Total** | **~14–15 GB, tight** |

With the 9B at Q4 for Robot R, there's about 1 GB more headroom. Running the C1 model on the CPU instead (T16) frees its VRAM entirely.

### Later, only if the core set falls short

| ID | Model | File | Approx. size | Why |
|---|---|---|---|---|
| F4 | Gemma 4 26B A4B (MoE) | official QAT Q4_0 GGUF | 14.4 GB | Bigger model; needs expert layers in system RAM |
| F5 | Qwen3.6-35B-A3B (MoE) | UD-Q4_K_XL | ~19–20 GB | Second MoE family |
| R1 | Qwen3.5-27B or Gemma 4 31B (dense) | IQ3_XXS | ~11.5–12 GB | Big reference arm, stepped mode only |

### Method

The second step is new; it is cheap and deterministic:

1. **Fixed settings:** same prompts, sampling temperature 0, the same llama.cpp build, KV cache f16 **and** q8_0 as two conditions.
2. **Offline prompt set.** The contexts G3a already logs from SB-04, SB-05 and S001-style runs are sent to every candidate with no Godot running. Scores:
   - **decision agreement** with the same model at higher precision (F1 against F2, N3 against N2);
   - valid output before any repair, repair rate, valid-action rate;
   - commitments kept (D-51);
   - tokens/s for prompt and generation, and VRAM.
3. **Finalists** run SB-04 and S001 live and stepped, for p50/p95 latency against the 4 s deadline, T25 frame times with the model running, and scenario quality (D-20).
4. **MoE candidates** (later set) sweep `--n-cpu-moe` (or `--fit`) to find the setting that leaves room for Godot and the NPC model, then report speed at that setting, not at the whole-card best case.

**Record per run:** model file name, quant type, SHA-256, llama.cpp build and KV cache type, in the run manifest, so every result says exactly which file produced it.

## Sources

- Google, Gemma 4 model overview and QAT checkpoints, memory table: https://ai.google.dev/gemma/docs/core
- Unsloth, Gemma 4 QAT (conversion caveat, KLD figures): https://unsloth.ai/docs/jp/moderu/gemma-4/qat
- Unsloth, Qwen3.5 GGUF benchmarks (KLD per quant): https://unsloth.ai/docs/models/qwen3.5/gguf-benchmarks
- Glukhov, 16 GB VRAM benchmarks with llama.cpp (RTX 4080): https://www.glukhov.org/llm-performance/benchmarks/best-llm-on-16gb-vram-gpu/
- Qwen3.5-35B-A3B on a 16 GB RTX 5060 Ti with `--n-cpu-moe`: https://ai-radar.it/article/qwen-3-5-35b-moe-40-token-s-su-rtx-5060-ti-con-contesto-100k
- MoE offload in llama.cpp (prefill behavior): https://huggingface.co/blog/Doctor-Shotgun/llamacpp-moe-offload-guide
- `--n-cpu-moe` vs the expert cache and `--fit`: https://www.developersdigest.tech/blog/llama-cpp-moe-offload-n-cpu-moe-vs-moe-cache-2026
- Lee et al., quantized instruction-tuned LLMs up to 405B: https://arxiv.org/abs/2409.11055
- Roshaan et al., quantization and missed tool calls in small models: https://neurips.cc/virtual/2026/171153
- Kurt, llama.cpp quantization on Llama-3.1-8B-Instruct: https://arxiv.org/abs/2601.14277
- KV cache quantization reports: https://www.techplained.com/kv-cache-quantization · https://smcleod.net/2024/12/bringing-k/v-context-quantisation-to-ollama/ · https://github.com/ggml-org/llama.cpp/issues/21450
- Qwen3.5 small series (0.8B–9B, Apache 2.0): https://artificialanalysis.ai/articles/qwen3-5-small-models
