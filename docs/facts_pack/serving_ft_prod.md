# FACTS_PACK: serving_ft_prod (serving, UI, deployment, queues, local inference, fine-tuning)
As of 2026-11-06. Python 3.11+. Verified in throwaway venvs `/tmp/facts_serving_ft_prod` (py3.12) + `/tmp/facts_unsloth`:
fastapi 0.162.0 (starlette 1.10.0) · uvicorn 0.54.0 · sse-starlette 3.6.0 · gradio 6.31.0 · streamlit 1.67.0 · rq 3.0.0 · redis 8.1.0 · tenacity 9.2.1 · ollama 0.6.3 · litellm 1.108.1 · openai 3.46.0 · trl 1.17.1 · peft 0.21.2 · transformers 5.22.2 · bitsandbytes 0.50.2 · torch 2.15.0 · unsloth/unsloth_zoo 2026.11.3. Not installable here (CUDA-only/not attempted): vllm 0.33.0, llmcompressor 0.15.0, so those use docs + source.
TLS-blocked here (so GitHub sources were used): fastapi.tiangolo.com, gradio.app, docs.streamlit.io, docs.astral.sh, docs.vllm.ai, docs.unsloth.ai, ollama.com, docs.litellm.ai, render.com, railway.com, fly.io, research.google.com.

## 1. VERIFIED API SHAPES

### 1.1 FastAPI 0.162 + uvicorn 0.54: `lifespan`, SSE (native `fastapi.sse`, added in 0.135.0)
```python
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from openai import AsyncOpenAI

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.client = AsyncOpenAI()      # create once; reuse per request
    yield
    await app.state.client.close()
app = FastAPI(lifespan=lifespan)
@app.get("/chat", response_class=EventSourceResponse)   # sets text/event-stream
async def chat(q: str) -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(raw_data="Hel", event="delta")   # raw_data = no JSON quoting
```
- verified by: introspection + TestClient run (wire output `event: delta\ndata: Hel\n\n…`); source `fastapi/sse.py`; https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/server-sent-events.md
- Sharp edges: `ServerSentEvent(data="hi")` JSON-encodes to `data: "hi"` (quotes included), so use `raw_data=` for plain tokens. `data` and `raw_data` are mutually exclusive (ValueError). `id`/`event` must be single-line. SSE works on POST too.
- Manual alternative (also verified): `return StreamingResponse(gen(), media_type="text/event-stream")`, where `gen()` yields `f"data: {t}\n\n"`. `sse-starlette` 3.6.0 is still maintained, but it's no longer needed. Teach native `fastapi.sse`.
- Run with `uvicorn app:app --host 0.0.0.0 --port 8000` (or `fastapi run app.py`, which needs `fastapi[standard]`). `@app.on_event` is replaced by `lifespan`.

### 1.2 Gradio 6.31: `ChatInterface` with a streaming generator
```python
import gradio as gr

def respond(message: str, history: list[dict]):
    # history items: {"role": ..., "content": [{"type": "text", "text": ...}], "metadata":..., "options":...}
    partial = ""
    for delta in stream_tokens(message, history):   # your OpenAI streaming helper
        partial += delta
        yield partial            # yield the FULL text so far, not the delta

demo = gr.ChatInterface(fn=respond, title="Atlas")   # no type= (messages is the only format)
demo.launch()                                         # theme/css/js/head are launch() params now
```
- verified by: introspection (`inspect.signature(gr.ChatInterface.__init__)`, `gr.Chatbot.__init__`); `Chatbot.preprocess` round-trip test; `gradio/chat_interface.py`.
- Sharp edges: `type=` passed to `ChatInterface(...)`/`Chatbot(...)` raises **TypeError** (there's no `**kwargs`). History `content` arrives **normalized to a list of `{"type":"text","text":…}` parts** (even if you returned a plain string). **Don't pass `history` straight into `responses.create(input=…)`.** Flatten it first: `"".join(p["text"] for p in m["content"] if p.get("type")=="text")`. `fn` may return or yield a str, a dict message, a component, or a list. Other ChatInterface params: `multimodal`, `additional_inputs`, `save_history`, `examples`, `chatbot=gr.Chatbot(...)`.

### 1.3 Streamlit 1.67: `st.chat_message` + `st.write_stream`
```python
import streamlit as st

if "msgs" not in st.session_state:
    st.session_state.msgs = []
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
if prompt := st.chat_input("Ask Atlas"):
    st.session_state.msgs.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        stream = client.responses.create(model=MODEL, input=st.session_state.msgs, stream=True)
        text = st.write_stream(stream)        # returns the full str
    st.session_state.msgs.append({"role": "assistant", "content": text})
```
- verified by: introspection + `streamlit/elements/write.py` (it natively parses Responses events `response.output_text.delta` / `response.refusal.delta`, as well as Chat Completions chunks). Run with `streamlit run app.py`.
- Signatures: `st.chat_message(name, *, avatar=None, width="stretch")` and `st.write_stream(stream, *, cursor=None) -> list | str`.

### 1.4 Docker: uv's official Dockerfile pattern + compose healthcheck
```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
ENV UV_NO_DEV=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home app
USER app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```
- verified by: https://raw.githubusercontent.com/astral-sh/uv/main/docs/guides/integration/docker.md (the uv Docker guide, mirrored above). The image wasn't built here (no Docker daemon). Add `.venv` to `.dockerignore`. **Docker's own Python guide** (https://docs.docker.com/guides/python/containerize/) uses pip + Docker Hardened Images (`dhi.io/python:3.12`), **not uv**, so "Docker's official uv guidance" means the uv docs.
- `python:3.12-slim` is currently 3.12.16 on Debian **trixie** (Docker Hub, updated 2026-11-05). **It has no curl** (the official Dockerfile purges wget), so don't write `test: curl …` healthchecks.
- Compose (validated with `docker compose config -q`, v2.39): `depends_on: {redis: {condition: service_healthy}}`; the api healthcheck is `test: ["CMD","python","-c","import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=3)"]`; redis uses `test: ["CMD","redis-cli","ping"]`; also `interval/timeout/retries/start_period` (and `start_interval`, Compose ≥2.20.2). Image `redis:8` exists. Source: https://docs.docker.com/reference/compose-file/services/

### 1.5 GitHub Actions (current majors, checked via the GitHub API 2026-11-06)
```yaml
- uses: actions/checkout@v7                 # latest v7.0.1 (2026-07-20)
- uses: astral-sh/setup-uv@v10.3.3          # NO floating major tag; pin full version or SHA
  with: { enable-cache: true }             # default is "auto"
- run: uv sync --locked --all-extras --dev
- run: uv run pytest tests
# alternative without uv: actions/setup-python@v7 (latest v7.1.0, 2026-10-22)
```
- Sharp edge: `astral-sh/setup-uv@v10` **fails**. Floating major tags exist only up to `v7` (`git ls-remote`); from v8 on there are only full versions (`v8.0.0` … `v10.3.3`). The setup-uv README pins a SHA: `@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3`. uv's own GitHub guide still shows v9.0.0 (stale).

### 1.6 Queues: RQ 3.0 (not 2.x) + redis-py 8.1
```python
import os
from redis import Redis
from rq import Queue, Retry
from rq.job import Job, JobStatus

redis = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
q = Queue("llm", connection=redis)
job = q.enqueue(summarize_doc, doc_id, job_timeout=300, result_ttl=3600,
                retry=Retry(max=3, interval=[10, 30, 60]))
# later / another process:
job = Job.fetch(job.id, connection=redis)
if job.get_status() == JobStatus.FINISHED:
    print(job.return_value())
```
- verified by: introspection + fakeredis run (`Queue(..., is_async=False)` runs inline for tests). Worker: `rq worker llm --url redis://localhost:6379/0` (add `--with-scheduler` for `enqueue_in/at` and for `Retry(interval=…)`, because retried jobs wait in the `scheduled` state). `JobStatus` values: created, queued, started, finished, failed, deferred, scheduled, stopped, canceled, **rate_limited, ready_to_enqueue** (new in 3.0).
- RQ 3.0 (2026-10-28) breaking changes hit worker internals, dependents and `CronScheduler` (now local TZ). `rate_limit=` is now a reserved `enqueue` kwarg. Needs redis-py ≥5.0.1. **Workers need `fork()`**, so on Windows use WSL. Source: https://raw.githubusercontent.com/rq/rq/master/CHANGES.md
- redis-py 8.1: `Redis.from_url(url, decode_responses=True)` for str values; async is `redis.asyncio.Redis` (close with `await r.aclose()`).

### 1.7 tenacity 9.2 retry on OpenAI transient errors (the SDK already retries 2× by default: `OpenAI(max_retries=2)`)
```python
import openai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

@retry(retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError,
                                      openai.APITimeoutError, openai.InternalServerError)),
       wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(5), reraise=True)
def ask(prompt: str) -> str:
    return client.responses.create(model=MODEL, input=prompt).output_text
```
- verified by: introspection + run (`reraise=True` re-raises the last exception; without it you get `tenacity.RetryError`). Stats are in `ask.statistics`. Also `wait_exponential_jitter(initial, max, jitter)` and `AsyncRetrying`.

### 1.8 LiteLLM 1.108.1 Router fallbacks (same-provider fallback by default)
```python
from litellm import Router
router = Router(
    model_list=[{"model_name": "primary", "litellm_params": {"model": "openai/gpt-6.1-terra"}},
                {"model_name": "backup",  "litellm_params": {"model": "openai/gpt-6-luna"}}],
    fallbacks=[{"primary": ["backup"]}], num_retries=2, timeout=30)
r = router.responses(model="primary", input="hi")        # Responses API; r.output_text
c = router.completion(model="primary", messages=[{"role": "user", "content": "hi"}])
```
- verified by: introspection + offline run with `mock_response=` and `mock_testing_fallbacks=True` (the fallback to `backup` was observed on `.completion`). `.responses`/`.aresponses` exist (`litellm/router.py` L2249-2252) and return `ResponsesAPIResponse` with `.output_text`. Other kwargs: `context_window_fallbacks`, `content_policy_fallbacks`, `default_fallbacks`, `allowed_fails`, `cooldown_time`, `routing_strategy`.
- Sharp edges: LiteLLM's bundled cost map knows `gpt-6-luna` but **not `gpt-6.1-terra`**, so cost tracking falls back to unknown. **Supply-chain incident:** litellm **1.82.7 and 1.82.8 on PyPI were compromised** (2026-03-24, https://github.com/BerriAI/litellm/issues/24518); both are now removed. Teach pinning plus a lockfile (`uv.lock`). Status: active, weekly releases.

### 1.9 Ollama (server; python lib 0.6.3): OpenAI-compatible base_url swap
```python
from openai import OpenAI
local = OpenAI(base_url="http://localhost:11434/v1/", api_key="ollama")   # key required but ignored
r = local.responses.create(model="qwen3:4b", input="Say hi")              # stateless Responses only
print(r.output_text)
import ollama                                                              # native lib alternative
vecs = ollama.embed(model="nomic-embed-text", input=["a", "b"]).embeddings
```
- verified by: https://raw.githubusercontent.com/ollama/ollama/main/docs/api/openai-compatibility.mdx (`/v1/responses` added in Ollama v0.13.3; `/v1/chat/completions` and `/v1/embeddings` are also there) + introspection of `ollama.chat`/`ollama.embed(model, input, truncate, options, keep_alive, dimensions)`.
- Sharp edges: **no `previous_response_id` or `conversation`** (stateless only), so re-send the history yourself. Install: macOS/Linux `curl -fsSL https://ollama.com/install.sh | sh` (or Ollama.dmg / `brew install ollama`); Windows `irm https://ollama.com/install.ps1 | iex`. Then `ollama pull <tag>`. Cloud models (`*:cloud`, `https://ollama.com/v1` + `OLLAMA_API_KEY`) are optional, not local.

### 1.10 llama.cpp (rolling builds, latest b12177 on 2026-11-06)
```bash
brew install llama.cpp                       # or winget install llama.cpp / curl -LsSf https://llama.app/install.sh | sh
python convert_hf_to_gguf.py ./my-model --outfile my-model-bf16.gguf --outtype bf16   # repo root script
llama-quantize my-model-bf16.gguf my-model-Q4_K_M.gguf Q4_K_M
llama-server -m my-model-Q4_K_M.gguf --port 8080     # DEFAULT PORT IS NOW 9931, not 8080
# OpenAI-compatible: /v1/chat/completions, /v1/responses, /v1/embeddings, /health
```
- verified by: `tools/server/README.md` ("by default listens on `127.0.0.1:9931`"), `tools/quantize/README.md`, the CMake targets `llama-server`, `llama-quantize` and `llama-cli` (all still built), and `docs/install.md`. The README now leads with a unified **`llama cli` / `llama serve -hf <repo>`** app (llama.app). The hyphenated binaries still exist. Prefer the hyphenated names plus a note.

### 1.11 vLLM 0.33.0: `vllm serve` (NVIDIA CUDA; Python 3.11–3.14)
```bash
uv venv --python 3.12 --seed && uv pip install vllm --torch-backend=auto
vllm serve Qwen/Qwen3-0.6B --dtype half --api-key "$VLLM_API_KEY"   # http://localhost:8000/v1
```
- Client: `OpenAI(base_url="http://localhost:8000/v1", api_key=os.environ["VLLM_API_KEY"])`, and then `client.responses.create(...)` works (vLLM serves `/v1/responses`, `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/messages`). Docs examples use `api_key="EMPTY"` when no `--api-key` is set.
- **Colab feasibility: YES on T4.** Requirement is "compute capability 7.5 or higher (e.g., T4…)". But T4 has no bf16: vLLM raises "Bfloat16 is only supported on GPUs with compute capability of at least 8.0 … `--dtype=half`", so **pass `--dtype half`** (`vllm/platforms/cuda.py`). Keep to models ≤~3B on a 16 GB T4 (rule of thumb, ⚠ verify). Mac: `vllm-metal` exists (out of scope), so use the llama-server fallback.
- verified by: https://raw.githubusercontent.com/vllm-project/vllm/main/docs/getting_started/quickstart.md, `docs/serving/online_serving/README.md`, `docs/getting_started/installation/gpu.cuda.inc.md`; PyPI 0.33.0 (2026-11-02).

### 1.12 llm-compressor 0.15.0 (replaces archived autoawq). Show as an optional/prose block
`from llmcompressor import oneshot` + `from llmcompressor.modifiers.quantization import QuantizationModifier` (also `GPTQModifier`, `AWQModifier`). Pattern: load an HF model → `oneshot(model=model, recipe=QuantizationModifier(targets="Linear", scheme="FP8_BLOCK", ignore=["lm_head"]))` → `model.save_pretrained(dir)` (compressed-tensors format) → `vllm serve dir`. Schemes include W4A16 (int4 GPTQ/AWQ), W8A8 int8/fp8, NVFP4, MXFP4. It needs a CUDA GPU and isn't introspected here (source: README https://raw.githubusercontent.com/vllm-project/llm-compressor/main/README.md). Mark the code `# fragment`.

### 1.13 Fine-tuning: Unsloth 2026.11.3 + TRL 1.17.1 + PEFT 0.21.2 + transformers 5.22.2
```python
from unsloth import FastLanguageModel          # import unsloth FIRST (it patches trl/transformers)
from trl import SFTConfig, SFTTrainer
model, tokenizer = FastLanguageModel.from_pretrained(model_name="unsloth/Qwen3-4B-Instruct-2507",  # HF: apache-2.0
    max_seq_length=2048, load_in_4bit=True)        # Unsloth's kwarg is max_seq_length
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16, lora_dropout=0,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth", random_state=3407)
trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=ds,   # NOT tokenizer=
    args=SFTConfig(output_dir="outputs", max_length=2048, per_device_train_batch_size=2,
                   gradient_accumulation_steps=4, max_steps=60, learning_rate=2e-4,
                   warmup_steps=5, optim="adamw_8bit", logging_steps=1, report_to="none"))
trainer.train()
model.save_pretrained_gguf("gguf_out", tokenizer, quantization_method="q4_k_m")   # → Ollama/llama.cpp
```
- verified by: Unsloth source `unsloth/models/loader.py` (`from_pretrained(model_name, max_seq_length=2048, dtype=None, load_in_4bit=True, load_in_8bit=False, load_in_16bit=False, full_finetuning=False, token=None…)`), `models/llama.py` get_peft_model defaults (r=16, lora_alpha=16), `save.py` `unsloth_save_pretrained_gguf(save_directory, tokenizer, quantization_method="fast_quantized"…)`. TRL/PEFT/BnB were introspected and constructed (TypeErrors below confirmed).
- **TRL sharp edges:** `SFTConfig(max_length=…)` (default 1024). **`max_seq_length` raises TypeError** (removed). **`warmup_ratio` raises TypeError**: transformers v5 dropped it, so use `warmup_steps` (accepts a float fraction, e.g. 0.03). SFTTrainer has **no `tokenizer=`**, so use `processing_class=` (also valid in trl 0.22.2). `report_to` defaults to `"none"`, `bf16` to None (auto). `assistant_only_loss=True` / `completion_only_loss` handle loss masking. Datasets: `{"messages":[…]}` conversational or `{"prompt","completion"}`. Minimal SFT: `SFTTrainer(model="Qwen/Qwen3-0.6B", train_dataset=…, peft_config=LoraConfig())` (TRL docs).
- **PEFT:** `LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM")`. Defaults are r=8, lora_alpha=8, task_type=None.
- **transformers v5 BnB:** `AutoModelForCausalLM.from_pretrained(id, quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True), dtype="auto", device_map="auto")`. The `load_in_4bit=` **kwarg on from_pretrained is removed**, `torch_dtype` is deprecated in favour of `dtype`, and `use_auth_token` becomes `token` (MIGRATION_GUIDE_V5.md). bitsandbytes 0.50.2.
- **Unsloth Colab notebooks** pin **`transformers==4.57.6`, `trl==0.22.2`** in their install cell (gpt-oss and Llama-3.2 notebooks, metadata `gpuType: "T4"`). **Tell learners to run the notebook's own install cell, not `pip install -U`.** Local install: `uv pip install unsloth --torch-backend=auto` (Linux/WSL; Windows: `uv pip install torchao` first). Unsloth now also runs on macOS via **MLX** (a different code path: `FastLanguageModel.from_pretrained` dispatches to `_mlx_from_pretrained`), so don't promise identical behaviour on a Mac. There's also a new "Unsloth Studio" web UI / Desktop app.

### 1.14 uv 0.13.7 (PyPI 2026-11-03)
`curl -LsSf https://astral.sh/uv/install.sh | sh` → `uv init atlas` → `uv add "openai>=3.46" fastapi` → `uv run python app.py` / `uv run pytest` → `uv sync --locked` (CI/Docker) → `uv lock --upgrade-package openai`. Also `uv add -r requirements.txt`. The venv plus `uv.lock` are created on the first `uv run`/`uv sync`/`uv lock`. Source: https://raw.githubusercontent.com/astral-sh/uv/main/docs/guides/projects.md


## 2. IDS / VERSIONS / PRICES (as of 2026-11-06; verify at the linked page before quoting)
- **Ollama tags (all exist; `https://registry.ollama.ai/v2/library/<name>/manifests/<tag>` returned 200; download sizes):** gpt-oss:20b 13.8 GB · gpt-oss:120b 65.4 GB · gemma4 (=e4b) 6.6 · gemma4:e2b 4.6 · gemma3:270m/1b/4b 0.29/0.81/3.4 · qwen3:0.6b/1.7b/4b/8b 0.5/1.4/2.5/5.2 · qwen3.5:0.8b/2b/4b 1.3/2.7/3.3 · llama3.2:1b/3b 1.3/2.0 · llama3.1:8b 4.9 · phi4-mini 2.5. Embeddings: nomic-embed-text 0.27 · embeddinggemma 0.62 · qwen3-embedding:0.6b 0.64. **8 GB-RAM option: `qwen3:4b` or `llama3.2:3b`**. gpt-oss:20b needs a ≥16 GB machine (rule of thumb, ⚠ verify).
- **gpt-oss on HF:** `openai/gpt-oss-20b` and `openai/gpt-oss-120b` are **Apache-2.0, not gated**, ship a `USAGE_POLICY` file and MXFP4 weights. Unsloth mirrors `unsloth/gpt-oss-20b` (Apache-2.0). Source: https://huggingface.co/api/models/openai/gpt-oss-20b
- **Google Cloud Run free tier** (request-based billing = default; us-central1 tier; per billing account per month): **180,000 vCPU-s, 360,000 GiB-s, 2M requests**. Instance-based billing: 240,000 vCPU-s / 450,000 GiB-s. Needs a billing account. https://cloud.google.com/run/pricing
- **Fly.io: NO free tier** ("New organizations don't have a free tier or a monthly free usage allowance"). New accounts get a **$1 trial credit valid for 7 days**, no card. Trial Machines **stop after 5 minutes**, max `shared-cpu-2x`/4 GB. Source: https://raw.githubusercontent.com/superfly/docs/main/about/pricing.mdx + `about/free-trial.mdx`
- **Hugging Face Spaces:** Static Spaces are free. **Gradio/Docker Spaces on compute need a paid plan (PRO $9/mo)**. Exception: free personal accounts (verified email, >30 days old) can host **up to 2 Gradio Spaces on ZeroGPU**. Free hardware sleeps when idle. https://huggingface.co/docs/hub/spaces-overview, …/spaces-zerogpu, https://huggingface.co/pricing
- **Render, Railway: UNVERIFIED.** render.com and railway.com failed TLS here and no public docs mirror was found. Writers: prose only, e.g. "check current free-tier terms at render.com/pricing / railway.com/pricing (⚠ verify)". No numbers.
- **Colab free T4: indirectly verified only.** Unsloth's official "free" notebooks set `gpuType: "T4"`. The Colab FAQ failed TLS. Say "free Colab GPUs (typically a T4) when available; quotas vary (⚠ verify)".
- **PyPI latest:** vllm 0.33.0 (11-02), llmcompressor 0.15.0 (10-28), unsloth 2026.11.3 (11-06), litellm 1.108.1 (11-05), uv 0.13.7, gradio 6.31.0, streamlit 1.67.0, fastapi 0.162.0, rq 3.0.0 (10-28), redis 8.1.0, tenacity 9.2.1, ollama-python 0.6.3; llama.cpp build b12177. **autoawq is archived** (GitHub `archived: true`).

## 3. DON'T USE (→ replacement)
- Gradio `type="messages"` (TypeError in 6.x) → omit it. Raw Gradio `history` as `input=` → flatten its parts first. `@app.on_event` → `lifespan`. `sse-starlette` as the default → `fastapi.sse` (optional extra).
- `HEALTHCHECK`/compose `curl -f …` on `python:3.12-slim` → a Python `urllib` probe (slim has no curl).
- `astral-sh/setup-uv@v10` (no such tag) → `@v10.3.3` or the SHA. `actions/checkout@v4` / `setup-python@v5` → `@v7`.
- TRL `SFTConfig(max_seq_length=…)` → `max_length`. `warmup_ratio` → `warmup_steps=<float>`. `SFTTrainer(tokenizer=…)` → `processing_class=`.
- transformers `from_pretrained(load_in_4bit=True)` → `quantization_config=BitsAndBytesConfig(...)`. `torch_dtype` → `dtype`. `use_auth_token` → `token`.
- `autoawq` (archived 2025) → `llmcompressor` (`AWQModifier`/`GPTQModifier`). Assuming llama-server listens on 8080 → pass `--port` (default is now 9931).
- Ollama `previous_response_id`/`conversation` (unsupported) → re-send history. `ollama.embeddings(prompt=)` (legacy) → `ollama.embed(input=)`.
- vLLM bf16 default on T4 → `--dtype half`. litellm `1.82.7`/`1.82.8` (compromised, deleted) → a current pin + `uv.lock`.
- "RQ 2.x" pins → `rq>=3.0` (same Queue/enqueue/Worker/Job API). "Fly.io free allowance" / "free CPU Gradio Space" → the §2 facts.

## 4. ⚠ VERIFY RESOLUTIONS (my scope)
- D034 | ~20-line Gradio UI "hosted free (HF Spaces)" | **CORRECTED**: a free account can host it only as a **ZeroGPU** Gradio Space (max 2; account >30 days, verified email). CPU Gradio Spaces need PRO ($9/mo). README YAML keys: `sdk: gradio`, `sdk_version`, `app_file: app.py`, `python_version` (**defaults to 3.10, so set "3.12"**), `title`, `emoji`. The API key goes in Space Secrets.
- D079 | Gradio 6 chat, no `type=` | **CONFIRMED** (TypeError if passed). Also: history content is a list of `{"type":"text"}` parts, so flatten it. Streamlit `st.write_stream` natively consumes Responses streams.
- D084 | LLM gateways (LiteLLM-class) | **CONFIRMED**: litellm 1.108.1 `Router(model_list, fallbacks=[{"primary":["backup"]}])` incl. `.responses()`. Add the 2026-03 supply-chain note.
- D091 | open-weight families incl. gpt-oss | **CONFIRMED**: gpt-oss-20b/120b are Apache-2.0 and ungated on HF; Ollama `gpt-oss:20b` (13.8 GB).
- D091 | Ollama model tags | **CONFIRMED** (§2 list, registry 200). 8 GB option: `qwen3:4b`/`llama3.2:3b`. Embedding model: `nomic-embed-text` or `embeddinggemma`.
- D092 | llama.cpp tools | **CORRECTED**: `llama-server`/`llama-quantize`/`llama-cli`/`convert_hf_to_gguf.py` all exist, but **llama-server's default port is 9931** and the README now promotes a unified `llama serve`/`llama cli` app.
- D092 | autoawq → llm-compressor | **CONFIRMED**: AutoAWQ repo archived; llmcompressor 0.15.0 `oneshot` + modifiers.
- D093 | vLLM Colab GPU path | **CONFIRMED with caveat**: T4 meets CC ≥7.5, but needs `--dtype half`. Colab's free-GPU availability is UNVERIFIABLE (prose + ⚠ verify). Mac fallback: `llama-server`.
- D095 | Unsloth + TRL SFT on Colab, "needs NVIDIA" | **CORRECTED**: official free Colab T4 notebooks exist (incl. **gpt-oss-20B** with `load_in_4bit=True`). Use the notebook's pinned install cell (transformers 4.57.6 / trl 0.22.2). Unsloth also runs on macOS (MLX), AMD and Intel now, but the course's Colab path is CUDA. GGUF export: `model.save_pretrained_gguf(dir, tokenizer, quantization_method="q4_k_m")`.

## 5. VERIFIED LINKS (each fetched with HTTP 200 on 2026-11-06)
- https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/server-sent-events.md: FastAPI native SSE (added 0.135.0)
- https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/advanced/events.md: FastAPI lifespan
- https://raw.githubusercontent.com/gradio-app/gradio/main/guides/05_chatbots/01_creating-a-chatbot-fast.md: Gradio ChatInterface guide
- https://huggingface.co/docs/hub/spaces-overview: Spaces plans, hardware, sleep
- https://huggingface.co/docs/hub/spaces-config-reference: Spaces README YAML keys
- https://huggingface.co/docs/hub/spaces-zerogpu: ZeroGPU free-account limits
- https://huggingface.co/pricing: HF PRO $9/mo
- https://raw.githubusercontent.com/astral-sh/uv/main/docs/guides/integration/docker.md: uv in Docker
- https://raw.githubusercontent.com/astral-sh/uv/main/docs/guides/projects.md: uv init/add/run/lock
- https://docs.docker.com/reference/compose-file/services/: compose healthcheck, depends_on conditions
- https://hub.docker.com/_/python: official python image tags (3.12-slim = trixie)
- https://raw.githubusercontent.com/astral-sh/setup-uv/main/README.md: setup-uv v10.3.3 usage (SHA pin)
- https://raw.githubusercontent.com/rq/rq/master/CHANGES.md: RQ 3.0 changes
- https://github.com/BerriAI/litellm/issues/24518: LiteLLM 1.82.7/1.82.8 compromise
- https://raw.githubusercontent.com/ollama/ollama/main/docs/api/openai-compatibility.mdx: Ollama /v1 incl. Responses
- https://raw.githubusercontent.com/ollama/ollama/main/README.md: Ollama install
- https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md: llama-server (port 9931, /v1/responses)
- https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/quantize/README.md: convert + llama-quantize
- https://raw.githubusercontent.com/vllm-project/vllm/main/docs/getting_started/quickstart.md: vllm install/serve
- https://raw.githubusercontent.com/vllm-project/llm-compressor/main/README.md: llm-compressor oneshot
- https://raw.githubusercontent.com/unslothai/unsloth/main/README.md: Unsloth install + free notebooks
- https://huggingface.co/docs/trl/sft_trainer: TRL SFTTrainer/SFTConfig
- https://huggingface.co/docs/transformers/quantization/bitsandbytes: BitsAndBytesConfig
- https://huggingface.co/openai/gpt-oss-20b: gpt-oss-20b model card (Apache-2.0)
- https://cloud.google.com/run/pricing: Cloud Run pricing + free tier

## ADDENDUM (2026-11-07, orchestrator, via the registry manifests API)
- `qwen3:4b` (model layer sha256:3e4cb1417446…) and `qwen3:4b-instruct-2507-q4_K_M` (sha256:85e4a5b7b8ef…, the same as `qwen3:4b-instruct`) are **different models**. Both are 2.5 GB, and `qwen3:4b-instruct-2507` returns 404. Phase 10 uses `qwen3:4b-instruct-2507-q4_K_M` everywhere, because it is the Ollama build of `Qwen/Qwen3-4B-Instruct-2507`, which D95 fine-tunes.
