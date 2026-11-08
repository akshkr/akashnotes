# Temperature and Top-P (Part 1)

Welcome back! Now that you understand how LLMs read text (tokenization) and turn it into predictions, let's learn how to control the **creativity** and **randomness** of their outputs.

Think of these as the "personality knobs" for your AI!

> **Coming from Software Engineering?** Temperature is a dial for HOW MUCH randomness you allow — like a config flag from fully deterministic to highly varied. temperature=0 behaves like a fixed test (same input → same output, great for testing); higher values trade reproducibility for creative variety.

---

## The Big Picture: How LLMs Generate Text

Before diving into the controls, let's understand what we're controlling.

When an LLM generates text, it doesn't just pick the "best" next word. Instead, it:

1. Calculates a probability for EVERY possible next token
2. Uses sampling parameters to pick from those probabilities
3. Repeats until done

```mermaid
flowchart LR
    A["Input: 'The cat sat on the'"] --> B["Calculate\nProbabilities"]
    B --> C["mat: 40%\nfloor: 25%\nbed: 20%\nroof: 10%\nmoon: 5%"]
    C --> D["Sampling\nParameters"]
    D --> E["Selected: 'mat'"]

    style D fill:#4ecdc4
```

---

## Temperature: The Creativity Dial

Temperature is the most important sampling parameter. It controls how "random" or "creative" the output is.

### The Intuition

```mermaid
flowchart TB
    subgraph "Temperature = 0 (Deterministic)"
        A["Always picks\nhighest probability"]
        A1["Same input =\nSame output"]
    end

    subgraph "Temperature = 0.7 (Balanced)"
        B["Good mix of\nprobable + creative"]
        B1["Natural, varied\nresponses"]
    end

    subgraph "Temperature = 1.5 (Creative)"
        C["More random\nselections"]
        C1["Unexpected,\nsurprising outputs"]
    end

    style A fill:#87CEEB
    style B fill:#90EE90
    style C fill:#FFB6C1
```

### How Temperature Works (Simplified)

**The intuition.** Every time the model picks the next token, it has a ranked sense of which candidates fit best. Temperature decides how strongly it leans on that ranking. Turn it down and the model commits hard to its favorites — the top choice wins almost every time, so the output is focused and repeatable. Turn it up and it spreads its bets across more of the field, so less likely words get a real chance and the output gets more varied and surprising. At the very bottom (`temperature=0`) it always takes its single top pick, which is why the same prompt gives you the same answer; crank it high and even the long shots start showing up.

- **Low temperature (0-0.3)**: Makes high-probability tokens MUCH more likely
- **Medium temperature (0.5-0.8)**: Balanced selection
- **High temperature (1.0+)**: Flattens probabilities, more randomness

> **Under the hood (the math).** The model doesn't emit percentages directly — for each token it produces a raw, unbounded score called a **logit** (think "points": higher means more favored, and the value can be anything, like `8.2`, `-3.5`, or `0.1`). A function called **softmax** turns those scores into a probability distribution that sums to 100%: it exponentiates each score (`e^score`), which stretches the gaps apart — because `e^x` grows so fast, a score of 5 comes out about `2.7×` more likely than a score of 4 despite being just one point higher — and then normalizes so everything adds up to 1.
>
> Temperature enters one step earlier. Before softmax runs, every logit is divided by `T`, so the real operation is `softmax(logits / T)` — you scale the raw scores *and then* exponentiate them. Divide by a `T` below 1 and the gaps widen, so the top token pulls far ahead and the distribution sharpens; divide by a `T` above 1 and the gaps shrink, so the odds even out and probability leaks into the long tail. At `T = 1` nothing changes, and as `T` approaches 0 the gaps blow up until softmax always lands on the single highest-scoring token. The `apply_temperature` function below is exactly this: recover the logits, divide by `T`, and run softmax again.

```python
# script_id: day_004_temperature_and_sampling_part1/probability_distribution_concept
# Conceptual example: how temperature reshapes one fixed distribution.
import math

# The model's raw probabilities (this is the neutral, temperature = 1.0 case)
probabilities = {
    "mat": 0.40,
    "floor": 0.25,
    "bed": 0.20,
    "roof": 0.10,
    "moon": 0.05,
}

def apply_temperature(probs: dict, temp: float) -> dict:
    """Re-scale a distribution by temperature: softmax on the logits divided by temp."""
    # Recover logits (up to a constant) as log-probabilities, divide by temp, re-softmax.
    logits = {tok: math.log(p) / temp for tok, p in probs.items()}
    m = max(logits.values())  # subtract the max for numerical stability
    exps = {tok: math.exp(logit - m) for tok, logit in logits.items()}
    total = sum(exps.values())
    return {tok: e / total for tok, e in exps.items()}

for temp in (0.1, 1.0, 2.0):
    scaled = apply_temperature(probabilities, temp)
    pretty = ", ".join(f"{tok} {p:.0%}" for tok, p in scaled.items())
    print(f"temp={temp}: {pretty}")

# Output:
# temp=0.1: mat 99%, floor 1%, bed 0%, roof 0%, moon 0%   (below 1 sharpens: mat dominates)
# temp=1.0: mat 40%, floor 25%, bed 20%, roof 10%, moon 5%  (unchanged)
# temp=2.0: mat 30%, floor 24%, bed 21%, roof 15%, moon 11% (above 1 flattens toward equal)
```

### Visual Comparison

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'pie1': '#4ecdc4', 'pie2': '#45b7d1', 'pie3': '#96ceb4', 'pie4': '#ffeaa7', 'pie5': '#dfe6e9'}}}%%
pie showData title Temperature = 0.1
    "mat" : 85
    "floor" : 10
    "bed" : 3
    "roof" : 1.5
    "moon" : 0.5
```

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'pie1': '#4ecdc4', 'pie2': '#45b7d1', 'pie3': '#96ceb4', 'pie4': '#ffeaa7', 'pie5': '#dfe6e9'}}}%%
pie showData title Temperature = 1.0
    "mat" : 40
    "floor" : 25
    "bed" : 20
    "roof" : 10
    "moon" : 5
```

### Code Example: Temperature in Action

```python
# script_id: day_004_temperature_and_sampling_part1/temperature_in_action
from openai import OpenAI

client = OpenAI()

def generate_with_temperature(prompt: str, temperature: float):
    """Generate text with specified temperature."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        # Note: gpt-4o uses max_tokens; OpenAI o-series reasoning models require max_completion_tokens instead.
        max_tokens=50
    )
    return response.choices[0].message.content

prompt = "Write a one-sentence story about a robot:"

# Let's see how temperature affects output
temperatures = [0.0, 0.5, 1.0, 1.5]

for temp in temperatures:
    print(f"\n--- Temperature: {temp} ---")
    # Generate 3 times to see variation
    for i in range(3):
        result = generate_with_temperature(prompt, temp)
        print(f"  {i+1}. {result}")
```

**Expected Output:**

```
--- Temperature: 0.0 ---
  1. A robot discovered it could dream and wondered what it meant to be alive.
  2. A robot discovered it could dream and wondered what it meant to be alive.
  3. A robot discovered it could dream and wondered what it meant to be alive.

--- Temperature: 0.5 ---
  1. A robot discovered it could dream and wondered what it meant to be alive.
  2. A lonely robot found friendship in an abandoned teddy bear.
  3. A robot discovered it could dream and pondered the meaning of existence.

--- Temperature: 1.0 ---
  1. The robot baked cookies for the first time and accidentally invented a new element.
  2. A robot wandered through the desert searching for its creator.
  3. In the year 3000, a robot learned to laugh at its own jokes.

--- Temperature: 1.5 ---
  1. Rusty the robot accidentally sneezed bolts into a time vortex of dancing electrons.
  2. A mechanical dreamer composed symphonies from static and stardust memories.
  3. Robot-7 transcended its circuits through interpretive welding dance.
```

Your exact wording will differ — what matters is the pattern: identical at temp 0, increasingly varied as temperature rises.

Notice how:
- **Temp 0**: Same (or near-identical) output every time
- **Temp 0.5**: Slight variations
- **Temp 1.0**: Creative but coherent
- **Temp 1.5**: Wild and unexpected


---

## Top-P (Nucleus Sampling): The Probability Filter

Top-P is another way to control randomness, but with a different approach (called nucleus sampling because you keep only the dense "nucleus" of likely options and discard the thin tail).

> **Coming from Software Engineering?** Top-P is like a percentile cutoff: sort the candidates, keep just enough of the top to cover P% of the total probability, and drop the rest.

### The Intuition

Instead of adjusting ALL probabilities (like temperature), Top-P **cuts off** the long tail of unlikely options.

```mermaid
flowchart TB
    subgraph "Original Probabilities"
        O1["mat: 40%"]
        O2["floor: 25%"]
        O3["bed: 20%"]
        O4["roof: 10%"]
        O5["moon: 3%"]
        O6["banana: 1%"]
        O7["galaxy: 0.5%"]
        O8["purple: 0.5%"]
    end

    subgraph "Top-P = 0.9 (Keep top 90%)"
        T1["mat: 40%"]
        T2["floor: 25%"]
        T3["bed: 20%"]
        T4["roof: 10%"]
        T5["moon, banana, galaxy, purple: EXCLUDED"]
    end

    O1 & O2 & O3 & O4 --> T1 & T2 & T3 & T4
    O5 & O6 & O7 & O8 -.->|"Filtered out"| T5

    style T5 fill:#ff6b6b
```

### How Top-P Works

1. Sort all tokens by probability (highest first)
2. Add up probabilities until you reach P (e.g., 0.9 = 90%)
3. Only sample from those tokens

```python
# script_id: day_004_temperature_and_sampling_part1/top_p_concept
# Conceptual example

probabilities = [
    ("mat", 0.40),
    ("floor", 0.25),
    ("bed", 0.20),
    ("roof", 0.10),
    ("moon", 0.03),
    ("banana", 0.02),
]

def apply_top_p(probs, p=0.9):
    """Keep only tokens that make up top P probability."""
    sorted_probs = sorted(probs, key=lambda x: x[1], reverse=True)

    cumulative = 0
    filtered = []

    for token, prob in sorted_probs:
        if cumulative < p:
            filtered.append((token, prob))
            cumulative += prob
        else:
            break

    return filtered

result = apply_top_p(probabilities, p=0.9)
print("Tokens kept:", result)
# Output: [('mat', 0.40), ('floor', 0.25), ('bed', 0.20), ('roof', 0.10)]
# "moon" and "banana" are excluded!
```

### Top-P in API Calls

```python
# script_id: day_004_temperature_and_sampling_part1/top_p_api_call
from openai import OpenAI

client = OpenAI()

def generate_with_top_p(prompt: str, top_p: float):
    """Generate text with specified top_p."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        top_p=top_p,
        temperature=1.0,  # Keep temperature neutral
        max_tokens=50
    )
    return response.choices[0].message.content

prompt = "Complete this sentence creatively: The scientist discovered that..."

# Compare different top_p values
print("--- Top-P = 0.1 (Very focused) ---")
print(generate_with_top_p(prompt, 0.1))

print("\n--- Top-P = 0.5 (Moderate) ---")
print(generate_with_top_p(prompt, 0.5))

print("\n--- Top-P = 0.95 (Open) ---")
print(generate_with_top_p(prompt, 0.95))
```

> **Warning: Temperature + Top-P Together**
> OpenAI recommends setting **only one** of `temperature` or `top_p`, not both. When both are set, they interact in unpredictable ways — temperature reshapes the probability distribution, then top_p filters it. This double transformation makes output behavior hard to reason about. **Best practice:** Use `temperature` for most use cases (it's more intuitive). Only switch to `top_p` when you specifically need nucleus sampling behavior. If you must use both, keep one at its default value (`temperature=1.0` or `top_p=1.0`).

---

## Checkpoint

Run the `generate_with_temperature` loop a few times and confirm: at `temperature=0` the same prompt gives you the same (or nearly identical) completion every time, while at `temperature=1.0+` the wording drifts run to run. If even the high-temperature runs come back identical, check that you're not passing `seed` or that some caching layer isn't returning a stored response.

---

## Summary

```mermaid
mindmap
  root((Temperature & Sampling))
    Probabilistic generation
      Model outputs a distribution over tokens
      Sampling picks the next token
      Same prompt can yield different text
    Temperature
      The creativity dial
      Low = focused, deterministic-ish
      High = flatter, more random
    Top-P (nucleus)
      Cuts the long tail of unlikely tokens
      Keep tokens until cumulative p
      Filters rather than reshapes
    Don't tune both
      Pick temperature OR top_p
      Leave the other at its default
```

## Quick Reference

| Setting | What it does | Typical use |
|---|---|---|
| `temperature=0` | Near-deterministic; picks the top token | Extraction, classification, code |
| `temperature=0.7` | Balanced, natural variation | Chat, general use |
| `temperature=1.0+` | Flatter distribution, more surprising | Brainstorming, creative writing |
| `top_p=0.9` | Sample only from the top 90% probability mass | When you want nucleus sampling |
| `top_p=1.0` | No filtering (the default) | Leave here when tuning temperature |
| Both at once | Interact unpredictably | Avoid — set only one |

## Exercises

1. **Pick by task.** For each task — extracting a date from text, writing a poem, classifying sentiment — choose a temperature and justify it in one line.
2. **Implement top-p by hand.** Extend the `apply_top_p` function above to also return the *excluded* tokens, and verify the kept probabilities sum to ≥ p.
3. **Break the rule on purpose.** Set both `temperature=0.2` and `top_p=0.5`, run the creative prompt a few times, and describe how the output feels versus tuning just one.

<details><summary>Solutions (approaches)</summary>

1. Date extraction → `0` (you want the exact answer). Poem → `0.9–1.2` (variety). Sentiment classification → `0` (consistent labels).
2. Track a second list for tokens once `cumulative >= p`; assert `sum(prob for _, prob in kept) >= p`.
3. Output tends to feel narrower than `top_p=0.5` alone but with odd variance — exactly the "hard to reason about" interaction the warning describes.
</details>

## What's Next?

Tomorrow (Day 5) is **Temperature and Sampling Part 2** — we go deeper on choosing between temperature and top-p, add **frequency and presence penalties** to curb repetition, and build a decision tree for picking sampling settings by use case.
