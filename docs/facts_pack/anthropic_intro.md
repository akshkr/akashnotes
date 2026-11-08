# FACTS_PACK: anthropic_intro (used ONLY by D2 and D7, as a comparison)
As of 2026-11-06. Verified by introspecting `anthropic==2.6.0` (Python 3.11, installed in /tmp/facts_anthropic). No live calls; there is no key.

## 1. VERIFIED API SHAPE
```python
import anthropic                      # uv add anthropic   (SDK 2.6.0)
client = anthropic.Anthropic()        # reads ANTHROPIC_API_KEY
msg = client.messages.create(
    model="claude-haiku-5-5",         # cheapest current Claude for a comparison call
    max_tokens=200,                   # REQUIRED (unlike OpenAI's optional max_output_tokens)
    system="You are a concise assistant.",   # top-level, not a message role
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)
print(msg.content[0].text)            # content is a LIST of blocks
print(msg.usage.input_tokens, msg.usage.output_tokens, msg.stop_reason)
```
verified by: `inspect.signature(client.messages.create)` (params include model, max_tokens, messages, system, thinking, output_config, tools, stream), and the `Message` / `Usage` model fields.

## 2. SHARP EDGES for the comparison box
- `messages.create` in 2.6.0 has **no `temperature`/`top_p` parameters**. B_currency says API version 2026-10-21 rejects sampling params. Don't show them.
- `max_tokens` is required. `system` is a top-level parameter. `content` is a list of typed blocks. `stop_reason` corresponds to OpenAI's `status`/incomplete.
- Depth is set with `output_config={"effort": ...}` (and `thinking=`). Leave these out of the D2 hello; at most one line in D7.
- `client.messages.count_tokens(...)` exists.

## 3. IDS (literals present in SDK 2.6.0; prices from Anthropic's reference cached 2026-10-06, so ⚠ verify at https://www.anthropic.com/pricing before quoting)
| ID | Note | Input/Output per 1M (verify) |
|---|---|---|
| `claude-haiku-5-5` | cheapest; use for the D2 hello | $0.10 / $0.50 (≤100K-token prompts) |
| `claude-sonnet-5-5` | balanced | $2 / $10 |
| `claude-opus-5-5` | flagship | $4 / $20 |
| `claude-fable-5-1` | premium | $10 / $50 |

Older IDs still present in the SDK: `claude-opus-4-8`, `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`. Use bare aliases only; never date-suffixed IDs.

## 4. DON'T USE
Date-suffixed IDs; `budget_tokens`; temperature/top_p; assistant prefill.
