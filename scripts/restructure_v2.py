#!/usr/bin/env python3
"""Restructure the 100-day curriculum: reorder, renumber, and rename all days."""

import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Phase directories
PHASES = {
    "Phase_0_Getting_Started": os.path.join(BASE, "Phase_0_Getting_Started"),
    "Phase_1_LLM_Foundations": os.path.join(BASE, "Phase_1_LLM_Foundations"),
    "Phase_2_External_Knowledge": os.path.join(BASE, "Phase_2_External_Knowledge"),
    "Phase_3_Single_Agent": os.path.join(BASE, "Phase_3_Single_Agent"),
    "Phase_4_MultiAgent_Eval_Security": os.path.join(BASE, "Phase_4_MultiAgent_Eval_Security"),
    "Phase_5_Production": os.path.join(BASE, "Phase_5_Production"),
    "Phase_6_Career_Launch": os.path.join(BASE, "Phase_6_Career_Launch"),
}


def build_mapping():
    """Build the complete old -> new mapping.

    Returns list of (source_phase, old_dir_name, target_phase, new_day_num, new_slug).
    source_phase and target_phase are phase directory keys.
    """
    mapping = []
    p0 = "Phase_0_Getting_Started"
    p1 = "Phase_1_LLM_Foundations"
    p2 = "Phase_2_External_Knowledge"
    p3 = "Phase_3_Single_Agent"
    p4 = "Phase_4_MultiAgent_Eval_Security"
    p5 = "Phase_5_Production"
    p6 = "Phase_6_Career_Launch"

    # --- Phase 0: unchanged ---
    mapping.append((p0, "Day_001_ai_engineering_career_map", p0, 1, "ai_engineering_career_map"))

    # --- Phase 1: reorder testing (025) to after pydantic (020) ---
    # Days 002-020 unchanged
    for d in range(2, 21):
        slug = get_existing_slug(p1, d)
        mapping.append((p1, f"Day_{d:03d}_{slug}", p1, d, slug))

    # Day 025 -> Day 021
    slug_025 = get_existing_slug(p1, 25)
    mapping.append((p1, f"Day_025_{slug_025}", p1, 21, slug_025))

    # Day 021 -> Day 022, Day 022 -> Day 023, Day 023 -> Day 024, Day 024 -> Day 025
    for old, new in [(21, 22), (22, 23), (23, 24), (24, 25)]:
        slug = get_existing_slug(p1, old)
        mapping.append((p1, f"Day_{old:03d}_{slug}", p1, new, slug))

    # Day 026 unchanged
    slug_026 = get_existing_slug(p1, 26)
    mapping.append((p1, f"Day_026_{slug_026}", p1, 26, slug_026))

    # --- Phase 2: unchanged (Days 027-040) ---
    for d in range(27, 41):
        slug = get_existing_slug(p2, d)
        mapping.append((p2, f"Day_{d:03d}_{slug}", p2, d, slug))

    # --- Phase 3: renumber after merges (14 days: 041-054) ---
    # Day_041 -> 041, Day_042 -> 042
    for d in [41, 42]:
        slug = get_existing_slug(p3, d)
        mapping.append((p3, f"Day_{d:03d}_{slug}", p3, d, slug))

    # Day_043 (merged) -> 043 with new slug
    mapping.append((p3, "Day_043_max_iterations_part1", p3, 43, "max_iterations"))

    # Day_045 -> 044, 046 -> 045, ... 049 -> 048
    phase3_shifts = [(45, 44), (46, 45), (47, 46), (48, 47), (49, 48)]
    for old, new in phase3_shifts:
        slug = get_existing_slug(p3, old)
        mapping.append((p3, f"Day_{old:03d}_{slug}", p3, new, slug))

    # Day_050 (merged) -> 049 with new slug
    mapping.append((p3, "Day_050_checkpoints_persistence_part1", p3, 49, "checkpoints_persistence"))

    # Day_052 -> 050, 053 -> 051, 054 -> 052, 055 -> 053, 056 -> 054
    phase3_shifts2 = [(52, 50), (53, 51), (54, 52), (55, 53), (56, 54)]
    for old, new in phase3_shifts2:
        slug = get_existing_slug(p3, old)
        mapping.append((p3, f"Day_{old:03d}_{slug}", p3, new, slug))

    # --- Phase 4: reorder blocks (27 days: 055-081) ---
    # Block 1: Multi-agent + frameworks (old 057-065 -> new 055-063)
    new_num = 55
    for old in range(57, 66):
        slug = get_existing_slug(p4, old)
        mapping.append((p4, f"Day_{old:03d}_{slug}", p4, new_num, slug))
        new_num += 1

    # Block 2: Evaluation (old 070-075 -> new 064-069)
    for old in range(70, 76):
        slug = get_existing_slug(p4, old)
        mapping.append((p4, f"Day_{old:03d}_{slug}", p4, new_num, slug))
        new_num += 1

    # Block 3: Security (old 076-082 -> new 070-076)
    for old in range(76, 83):
        slug = get_existing_slug(p4, old)
        mapping.append((p4, f"Day_{old:03d}_{slug}", p4, new_num, slug))
        new_num += 1

    # Block 4: HITL (old 066-069 -> new 077-080)
    for old in range(66, 70):
        slug = get_existing_slug(p4, old)
        mapping.append((p4, f"Day_{old:03d}_{slug}", p4, new_num, slug))
        new_num += 1

    # Capstone (old 083 -> new 081)
    slug_083 = get_existing_slug(p4, 83)
    mapping.append((p4, f"Day_083_{slug_083}", p4, 81, slug_083))

    # --- Phase 5: reorder + new days (16 days: 082-097) ---
    # Old 084-091 -> New 082-089
    new_num = 82
    for old in range(84, 92):
        slug = get_existing_slug(p5, old)
        mapping.append((p5, f"Day_{old:03d}_{slug}", p5, new_num, slug))
        new_num += 1

    # Old 092 (rate limits) -> New 090
    slug_092 = get_existing_slug(p5, 92)
    mapping.append((p5, f"Day_092_{slug_092}", p5, 90, slug_092))

    # NEW days (already created at temporary numbers)
    mapping.append((p5, "Day_091_semantic_caching", p5, 91, "semantic_caching"))
    mapping.append((p5, "Day_092_model_fallback_strategies", p5, 92, "model_fallback_strategies"))

    # Old 093 -> New 093
    slug_093 = get_existing_slug(p5, 93)
    mapping.append((p5, f"Day_093_{slug_093}", p5, 93, slug_093))

    # Old 096 (prompt eng) -> New 094 (moved earlier)
    slug_096 = get_existing_slug(p5, 96)
    mapping.append((p5, f"Day_096_{slug_096}", p5, 94, slug_096))

    # Old 094 (MCP) -> New 095
    slug_094 = get_existing_slug(p5, 94)
    mapping.append((p5, f"Day_094_{slug_094}", p5, 95, slug_094))

    # Old 095 (Claude SDK) -> New 096
    slug_095 = get_existing_slug(p5, 95)
    mapping.append((p5, f"Day_095_{slug_095}", p5, 96, slug_095))

    # Old 097 -> New 097
    slug_097 = get_existing_slug(p5, 97)
    mapping.append((p5, f"Day_097_{slug_097}", p5, 97, slug_097))

    # --- Phase 6: unchanged (Days 098-100) ---
    for d in range(98, 101):
        slug = get_existing_slug(p6, d)
        mapping.append((p6, f"Day_{d:03d}_{slug}", p6, d, slug))

    return mapping


def get_existing_slug(phase_key, day_num):
    """Find the slug for an existing day directory."""
    phase_path = PHASES[phase_key]
    prefix = f"Day_{day_num:03d}_"
    for d in os.listdir(phase_path):
        if d.startswith(prefix):
            return d[len(prefix):]
    raise FileNotFoundError(f"No directory found for Day {day_num:03d} in {phase_key}")


def update_h1_heading(md_path, new_day_num):
    """Update the H1 heading to reflect the new day number."""
    with open(md_path, "r") as f:
        content = f.read()

    # Match patterns like "# Day 43: ..." or "# Max Iterations ..."
    # Replace "# Day NN:" with new number, or prepend day number if missing
    h1_match = re.match(r"^# (?:Day \d+[:\s—–-]+\s*)?(.+)", content)
    if h1_match:
        title = h1_match.group(1).strip()
        # Don't add "Day N:" prefix - keep titles clean
        # The day number is in the directory name
    return  # Don't modify H1s — they use descriptive titles, not day numbers


def main():
    print("Building mapping...")
    mapping = build_mapping()
    print(f"Mapping has {len(mapping)} entries")

    # Verify no duplicate targets
    targets = [(phase, num) for _, _, phase, num, _ in mapping]
    if len(targets) != len(set(targets)):
        dupes = [t for t in targets if targets.count(t) > 1]
        raise ValueError(f"Duplicate targets: {set(dupes)}")
    print("No duplicate targets - good!")

    # Verify all source dirs exist
    for src_phase, old_dir, _, _, _ in mapping:
        src_path = os.path.join(PHASES[src_phase], old_dir)
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source not found: {src_path}")
    print("All source directories exist - good!")

    # Stage all to temp
    temp_dir = os.path.join(BASE, "_temp_renumber")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    print("\nStaging all directories to temp...")
    for src_phase, old_dir, _, _, _ in mapping:
        src = os.path.join(PHASES[src_phase], old_dir)
        dst = os.path.join(temp_dir, f"{src_phase}__{old_dir}")
        shutil.move(src, dst)

    # Place all at new locations
    print("Placing at new locations...")
    for src_phase, old_dir, tgt_phase, new_num, new_slug in mapping:
        staged = os.path.join(temp_dir, f"{src_phase}__{old_dir}")
        new_dir_name = f"Day_{new_num:03d}_{new_slug}"
        dst = os.path.join(PHASES[tgt_phase], new_dir_name)
        shutil.move(staged, dst)

        # Rename .md file inside if slug changed
        old_slug = old_dir.split("_", 2)[2] if "_" in old_dir[4:] else old_dir
        for f in os.listdir(dst):
            if f.endswith(".md"):
                old_md = f
                new_md = f"{new_slug}.md"
                if old_md != new_md:
                    os.rename(os.path.join(dst, old_md), os.path.join(dst, new_md))
                break

    # Cleanup
    shutil.rmtree(temp_dir)
    print("Cleanup complete.")

    # Verify
    print("\n=== Final Structure ===")
    total = 0
    for name in sorted(PHASES.keys()):
        path = PHASES[name]
        days = sorted([d for d in os.listdir(path) if d.startswith("Day_")])
        total += len(days)
        if days:
            first = days[0].split("_")[1]
            last = days[-1].split("_")[1]
            print(f"  {name}: {len(days)} days (Day {first}-{last})")
    print(f"  TOTAL: {total} days")

    # Verify contiguous numbering
    all_days = []
    for name in sorted(PHASES.keys()):
        path = PHASES[name]
        for d in os.listdir(path):
            if d.startswith("Day_"):
                all_days.append(int(d.split("_")[1]))
    all_days.sort()

    expected = list(range(1, 101))
    if all_days == expected:
        print("\n  Numbering is contiguous 001-100!")
    else:
        missing = set(expected) - set(all_days)
        extra = set(all_days) - set(expected)
        if missing:
            print(f"\n  MISSING days: {sorted(missing)}")
        if extra:
            print(f"\n  EXTRA days: {sorted(extra)}")


if __name__ == "__main__":
    main()
