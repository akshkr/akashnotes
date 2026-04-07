# LLM-as-Judge — Part 2: Advanced Evaluation Techniques

Yesterday you built basic LLM-as-judge scoring and pairwise comparison. Today we go deeper: the failure modes that make naive judges unreliable, calibration techniques that fix them, multi-judge consensus for high-stakes evaluation, and cost-efficient strategies that don't blow your budget.

> **Coming from Software Engineering?** This is like building a reliable test suite — a single flaky test is worse than no test because it gives false confidence. LLM judges have systematic biases (like a linter that always flags a certain pattern even when it's fine). Today you learn to detect and compensate for those biases, use consensus across multiple judges (like requiring 2 of 3 reviewers to approve a PR), and optimize for cost the same way you'd optimize CI pipeline runtime.

---

## The Problem with Naive LLM Judges

Your Day 72 judge works — until it doesn't. LLM judges have well-documented biases that produce unreliable scores if you don't account for them.

### Position Bias

LLMs tend to prefer whichever response appears first (or last, depending on the model). This means pairwise comparisons can flip just by swapping the order.

```python
from openai import OpenAI
import json

client = OpenAI()

def demonstrate_position_bias(question: str, response_a: str, response_b: str) -> dict:
    """Show how position affects judge scoring."""

    prompt_template = """Compare these two responses to the question: "{question}"

Response {label_1}: {first}

Response {label_2}: {second}

Which response is better? Return JSON: {{"winner": "A" or "B", "reasoning": "..."}}"""

    # Order 1: A first
    result_1 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_template.format(
            question=question, label_1="A", label_2="B",
            first=response_a, second=response_b
        )}],
        response_format={"type": "json_object"},
        temperature=0
    )
    order_1 = json.loads(result_1.choices[0].message.content)

    # Order 2: B first (swap positions, keep labels)
    result_2 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_template.format(
            question=question, label_1="A", label_2="B",
            first=response_b, second=response_a
        )}],
        response_format={"type": "json_object"},
        temperature=0
    )
    order_2 = json.loads(result_2.choices[0].message.content)

    consistent = order_1["winner"] != order_2["winner"]  # Should flip if unbiased

    return {
        "a_first_winner": order_1["winner"],
        "b_first_winner": order_2["winner"],
        "consistent": consistent,
        "position_biased": not consistent
    }
```

### Verbosity Bias

LLM judges tend to rate longer, more detailed responses higher — even when the shorter response is more accurate or more appropriate.

```python
def detect_verbosity_bias(question: str, concise: str, verbose: str) -> dict:
    """Check if the judge prefers verbose responses regardless of quality."""

    prompt = f"""Rate both responses on a 1-5 scale for ACCURACY ONLY.
Ignore length, style, and detail. Focus purely on factual correctness.

Question: {question}

Response A (concise): {concise}

Response B (detailed): {verbose}

Return JSON: {{"a_score": 1-5, "b_score": 1-5, "reasoning": "..."}}"""

    result = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    scores = json.loads(result.choices[0].message.content)

    # If verbose always scores higher despite equal accuracy, that's bias
    return scores

# Example: Both are equally correct, but one is verbose
result = detect_verbosity_bias(
    question="What is the capital of France?",
    concise="Paris.",
    verbose="The capital of France is Paris, a city known as the City of Light, "
            "located in the north-central part of the country along the Seine River. "
            "Paris has been the capital since the late 10th century."
)
# A biased judge will score the verbose response higher despite equal accuracy
```

### Self-Enhancement Bias

Models tend to rate their own outputs higher than outputs from other models. If you use GPT-4o to judge GPT-4o vs. Claude outputs, expect bias toward GPT-4o.

**Mitigation**: Use a different model as judge than the one that generated the responses, or use multi-judge consensus.

---

## Calibration: Making Judges Reliable

Calibration means ensuring your judge's scores are meaningful and consistent. Without calibration, a "4 out of 5" from your judge might mean different things for different types of questions.

### Anchor-Based Calibration

Provide the judge with reference examples at known quality levels:

```python
CALIBRATION_ANCHORS = {
    "excellent": {
        "question": "Explain recursion in programming.",
        "response": "Recursion is when a function calls itself to solve a smaller "
                    "version of the same problem. Every recursive function needs a "
                    "base case (when to stop) and a recursive case (how to break the "
                    "problem down). Example: calculating factorial — factorial(5) = "
                    "5 * factorial(4), and factorial(1) = 1 is the base case.",
        "score": 5,
        "reasoning": "Accurate, clear, includes example, mentions base case."
    },
    "mediocre": {
        "question": "Explain recursion in programming.",
        "response": "Recursion is when a function calls itself. It's used in "
                    "programming for various tasks.",
        "score": 2,
        "reasoning": "Technically correct but lacks depth, no example, no base case."
    },
    "poor": {
        "question": "Explain recursion in programming.",
        "response": "Recursion is a loop that repeats until a condition is met.",
        "score": 1,
        "reasoning": "Confuses recursion with iteration. Factually incorrect."
    }
}

def calibrated_judge(question: str, response: str) -> dict:
    """Judge with calibration anchors for consistent scoring."""

    anchor_text = ""
    for level, anchor in CALIBRATION_ANCHORS.items():
        anchor_text += f"\n--- {level.upper()} example (score: {anchor['score']}) ---\n"
        anchor_text += f"Q: {anchor['question']}\n"
        anchor_text += f"A: {anchor['response']}\n"
        anchor_text += f"Why this score: {anchor['reasoning']}\n"

    prompt = f"""You are an expert evaluator. Score the following response on a 1-5 scale.

Use these calibration examples to anchor your scoring:
{anchor_text}

Now evaluate:
Question: {question}
Response: {response}

Return JSON: {{"score": 1-5, "reasoning": "...", "closest_anchor": "excellent/mediocre/poor"}}"""

    result = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    return json.loads(result.choices[0].message.content)
```

### Measuring Judge Reliability: Cohen's Kappa

Compare your LLM judge against human evaluators (or against itself across runs) to measure agreement:

```python
def cohens_kappa(judge_1_scores: list[int], judge_2_scores: list[int]) -> float:
    """Calculate Cohen's Kappa for inter-rater agreement (Landis & Koch, 1977).

    Returns:
        -1 to 1: <0 = worse than random, 0 = random, 0.21-0.40 = fair,
        0.41-0.60 = moderate, 0.61-0.80 = substantial, >0.80 = almost perfect
    """
    assert len(judge_1_scores) == len(judge_2_scores)
    n = len(judge_1_scores)
    categories = sorted(set(judge_1_scores + judge_2_scores))

    # Observed agreement
    agreements = sum(1 for a, b in zip(judge_1_scores, judge_2_scores) if a == b)
    p_observed = agreements / n

    # Expected agreement by chance
    p_expected = sum(
        (judge_1_scores.count(c) / n) * (judge_2_scores.count(c) / n)
        for c in categories
    )

    if p_expected == 1:
        return 1.0
    return (p_observed - p_expected) / (1 - p_expected)

# Usage: compare LLM judge vs human labels
human_scores = [5, 3, 4, 2, 5, 1, 4, 3, 5, 2]
llm_scores =   [5, 4, 4, 2, 5, 1, 3, 3, 5, 3]

kappa = cohens_kappa(human_scores, llm_scores)
print(f"Cohen's Kappa: {kappa:.3f}")
# > 0.6 = substantial agreement → judge is reliable enough for automated use
# 0.21-0.40 = fair agreement → judge needs better calibration or different prompt
# < 0.20 = slight/poor agreement → fundamentally rethink your evaluation approach
```

---

## Multi-Judge Consensus

For high-stakes evaluations, use multiple judges and aggregate their scores. This reduces the impact of any single judge's bias.

```python
from typing import Optional

def multi_judge_evaluate(
    question: str,
    response: str,
    models: list[str] = ["gpt-4o", "gpt-4o-mini"],
    threshold: float = 0.7
) -> dict:
    """Evaluate using multiple LLM judges with consensus scoring."""

    all_scores = []
    all_reasoning = []

    for model in models:
        result = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": f"""Rate this response 1-5.
Question: {question}
Response: {response}
Return JSON: {{"score": 1-5, "reasoning": "..."}}"""}],
            response_format={"type": "json_object"},
            temperature=0
        )
        parsed = json.loads(result.choices[0].message.content)
        all_scores.append(parsed["score"])
        all_reasoning.append({"model": model, **parsed})

    avg_score = sum(all_scores) / len(all_scores)
    score_variance = sum((s - avg_score) ** 2 for s in all_scores) / len(all_scores)

    return {
        "average_score": round(avg_score, 2),
        "scores": all_scores,
        "variance": round(score_variance, 2),
        "high_agreement": score_variance < 0.5,
        "passed": avg_score >= (threshold * 5),
        "details": all_reasoning
    }

# 💰 Cost note: 2 judges = 2x cost per evaluation.
# At GPT-4o ($2.50/1M in + $10/1M out) with ~500 tokens per eval:
# Single judge: ~$0.006/eval → $6/1000 evals
# Dual judge: ~$0.012/eval → $12/1000 evals
```

### Handling Disagreement

When judges disagree significantly, you need a tiebreaker strategy:

```python
def evaluate_with_tiebreaker(question: str, response: str) -> dict:
    """Two cheap judges + expensive tiebreaker when they disagree."""

    # Round 1: Two cheap judges
    cheap_results = multi_judge_evaluate(
        question, response,
        models=["gpt-4o-mini", "gpt-4o-mini"]
    )

    if cheap_results["high_agreement"]:
        return {**cheap_results, "tiebreaker_used": False}

    # Round 2: Expensive judge as tiebreaker (only when needed)
    tiebreaker = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"""Two evaluators disagreed on this response.
Scores were: {cheap_results['scores']}

Question: {question}
Response: {response}

Provide the definitive score. Return JSON: {{"score": 1-5, "reasoning": "..."}}"""}],
        response_format={"type": "json_object"},
        temperature=0
    )
    final = json.loads(tiebreaker.choices[0].message.content)

    return {
        "average_score": final["score"],
        "scores": cheap_results["scores"] + [final["score"]],
        "tiebreaker_used": True,
        "tiebreaker_reasoning": final["reasoning"]
    }

# 💰 Cost optimization: tiebreaker only fires ~20-30% of the time
# Effective cost: ~$0.004/eval instead of $0.012/eval for always using 2 expensive judges
```

---

## Cost-Efficient Evaluation at Scale

Running LLM-as-judge on every response is expensive. Here are strategies to keep costs manageable.

### Strategy 1: Sampling

Don't evaluate everything. Evaluate a random sample and extrapolate:

```python
import random

def sampled_evaluation(
    test_cases: list[dict],
    eval_fn: callable,
    sample_rate: float = 0.1,  # Evaluate 10% of cases
    min_samples: int = 30       # Statistical minimum
) -> dict:
    """Evaluate a sample and estimate population quality."""

    n_samples = max(min_samples, int(len(test_cases) * sample_rate))
    sample = random.sample(test_cases, min(n_samples, len(test_cases)))

    scores = [eval_fn(tc["question"], tc["response"])["score"] for tc in sample]

    mean = sum(scores) / len(scores)
    std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5

    return {
        "estimated_mean": round(mean, 2),
        "std_dev": round(std, 2),
        "confidence_interval": (round(mean - 1.96 * std / len(scores)**0.5, 2),
                                 round(mean + 1.96 * std / len(scores)**0.5, 2)),
        "samples_evaluated": len(scores),
        "total_cases": len(test_cases)
    }
```

### Strategy 2: Tiered Evaluation

Use cheap models for screening, expensive models for borderline cases:

```python
def tiered_evaluation(question: str, response: str) -> dict:
    """Cheap screening → expensive evaluation only for borderline cases."""

    # Tier 1: Fast, cheap screening with gpt-4o-mini
    screen = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""Quick quality check.
Question: {question}
Response: {response}
Return JSON: {{"score": 1-5, "confidence": "high" or "low"}}"""}],
        response_format={"type": "json_object"},
        temperature=0
    )
    screening = json.loads(screen.choices[0].message.content)

    # Clear pass (4-5) or clear fail (1-2) with high confidence → done
    if screening.get("confidence") == "high" and screening["score"] not in [3]:
        return {"score": screening["score"], "tier": "screening", "model": "gpt-4o-mini"}

    # Tier 2: Borderline cases get full evaluation with gpt-4o
    full = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"""Carefully evaluate this response.
Question: {question}
Response: {response}
Return JSON: {{"score": 1-5, "reasoning": "..."}}"""}],
        response_format={"type": "json_object"},
        temperature=0
    )
    result = json.loads(full.choices[0].message.content)

    return {"score": result["score"], "tier": "full", "model": "gpt-4o",
            "reasoning": result["reasoning"]}

# 💰 Cost: ~60-70% of cases resolved at Tier 1 (gpt-4o-mini: ~$0.0004/eval)
# Only 30-40% escalated to Tier 2 (gpt-4o: ~$0.006/eval)
# Blended cost: ~$0.002/eval vs $0.006/eval for always using gpt-4o (3x cheaper)
```

---

## Summary

| Technique | What It Solves | When to Use |
|-----------|---------------|-------------|
| Position swapping | Position bias in pairwise comparison | Always for A/B comparisons |
| Calibration anchors | Inconsistent scoring across different questions | When score reliability matters |
| Cohen's Kappa | Unknown judge reliability | Before trusting automated eval in production |
| Multi-judge consensus | Single-judge bias/noise | High-stakes evaluations (content publishing, safety) |
| Tiebreaker pattern | Cost of always using multiple judges | Balance cost vs. reliability |
| Sampled evaluation | Evaluating everything is too expensive | Large test sets (1000+) |
| Tiered evaluation | Expensive models for every eval | Production evaluation at scale |

---

## What's Next

You now have reliable, calibrated, cost-efficient evaluation. Next up: **RAGAS** — a specialized framework for evaluating RAG systems with metrics like faithfulness, answer relevancy, and context precision.

---
