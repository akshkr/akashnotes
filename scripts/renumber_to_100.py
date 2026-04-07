#!/usr/bin/env python3
"""Renumber 83-day structure to 100 days, inserting new day slots."""

import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Phase directories
PHASES = {
    "Phase_1_LLM_Foundations": os.path.join(BASE, "Phase_1_LLM_Foundations"),
    "Phase_2_External_Knowledge": os.path.join(BASE, "Phase_2_External_Knowledge"),
    "Phase_3_Single_Agent": os.path.join(BASE, "Phase_3_Single_Agent"),
    "Phase_4_MultiAgent_Eval_Security": os.path.join(BASE, "Phase_4_MultiAgent_Eval_Security"),
    "Phase_5_Production": os.path.join(BASE, "Phase_5_Production"),
}

# New phases to create
NEW_PHASES = {
    "Phase_0_Getting_Started": os.path.join(BASE, "Phase_0_Getting_Started"),
    "Phase_6_Career_Launch": os.path.join(BASE, "Phase_6_Career_Launch"),
}


def get_day_dirs(phase_path):
    """Get sorted list of day directories in a phase."""
    dirs = [d for d in os.listdir(phase_path) if d.startswith("Day_")]
    return sorted(dirs)


def rename_day_dir(phase_path, old_dir_name, new_day_num, new_topic_name=None):
    """Rename a day directory with a new number, optionally new topic name."""
    old_path = os.path.join(phase_path, old_dir_name)
    # Extract topic name from old dir if not provided
    if new_topic_name is None:
        parts = old_dir_name.split("_", 2)  # Day_NNN_topic
        new_topic_name = parts[2] if len(parts) > 2 else "unknown"
    new_dir_name = f"Day_{new_day_num:03d}_{new_topic_name}"
    new_path = os.path.join(phase_path, new_dir_name)

    # Also rename the .md file inside
    old_md = None
    for f in os.listdir(old_path):
        if f.endswith(".md"):
            old_md = f
            break

    os.rename(old_path, new_path)

    if old_md:
        new_md = f"{new_topic_name}.md"
        if old_md != new_md:
            os.rename(os.path.join(new_path, old_md), os.path.join(new_path, new_md))

    return new_path


def create_placeholder_day(phase_path, day_num, topic_name, title):
    """Create a new day directory with a placeholder .md file."""
    dir_name = f"Day_{day_num:03d}_{topic_name}"
    dir_path = os.path.join(phase_path, dir_name)
    os.makedirs(dir_path, exist_ok=True)
    md_path = os.path.join(dir_path, f"{topic_name}.md")
    with open(md_path, "w") as f:
        f.write(f"# Day {day_num}: {title}\n\n<!-- TODO: Content to be written -->\n")
    return dir_path


def main():
    # Step 1: Create new phase directories
    for name, path in NEW_PHASES.items():
        os.makedirs(path, exist_ok=True)
        print(f"Created {name}")

    # Step 2: Move all existing day dirs to temp location to avoid conflicts
    temp_dir = os.path.join(BASE, "_temp_renumber")
    os.makedirs(temp_dir, exist_ok=True)

    # Collect all existing days with their phase info
    existing_days = []  # (old_day_num, phase_name, dir_name, phase_path)
    for phase_name, phase_path in sorted(PHASES.items()):
        for d in get_day_dirs(phase_path):
            day_num = int(d.split("_")[1])
            existing_days.append((day_num, phase_name, d, phase_path))

    existing_days.sort(key=lambda x: x[0])

    # Move all to temp
    for day_num, phase_name, dir_name, phase_path in existing_days:
        src = os.path.join(phase_path, dir_name)
        dst = os.path.join(temp_dir, dir_name)
        shutil.move(src, dst)

    print(f"Moved {len(existing_days)} day dirs to temp")

    # Step 3: Define the mapping: old_day_num -> (new_day_num, new_phase_path)
    # And define new days to insert

    # Mapping structure:
    # Phase 0: Day 001 (NEW - Career Map)
    # Phase 1: Days 002-024 (old 001-023) + Day 025 (NEW - Testing) + Day 026 (NEW - Capstone)
    # Phase 2: Days 027-038 (old 024-035) + Day 039 (NEW - Cost) + Day 040 (NEW - Capstone)
    # Phase 3: Days 041-053 (old 036-048) + Day 054 (NEW - Debugging) + Day 055 (NEW - Capstone) + Day 056 (NEW - Career Checkpoint)
    # Phase 4: Days 057-081 (old 049-073) + Day 082 (NEW - Hardening) + Day 083 (NEW - Capstone)
    # Phase 5: Days 084-093 (old 074-083) + Day 094 (NEW - MCP) + Day 095 (NEW - Agent SDK) + Day 096 (NEW - Prompt Eng) + Day 097 (NEW - Capstone)
    # Phase 6: Day 098 (NEW - Interview) + Day 099 (NEW - Portfolio) + Day 100 (NEW - Launch)

    p0 = NEW_PHASES["Phase_0_Getting_Started"]
    p1 = PHASES["Phase_1_LLM_Foundations"]
    p2 = PHASES["Phase_2_External_Knowledge"]
    p3 = PHASES["Phase_3_Single_Agent"]
    p4 = PHASES["Phase_4_MultiAgent_Eval_Security"]
    p5 = PHASES["Phase_5_Production"]
    p6 = NEW_PHASES["Phase_6_Career_Launch"]

    # Build renumber map: old_day_num -> (new_day_num, target_phase_path)
    renumber_map = {}

    # Old 001-023 -> New 002-024 (Phase 1)
    for old in range(1, 24):
        renumber_map[old] = (old + 1, p1)

    # Old 024-035 -> New 027-038 (Phase 2)
    for old in range(24, 36):
        renumber_map[old] = (old + 3, p2)

    # Old 036-048 -> New 041-053 (Phase 3)
    for old in range(36, 49):
        renumber_map[old] = (old + 5, p3)

    # Old 049-073 -> New 057-081 (Phase 4)
    for old in range(49, 74):
        renumber_map[old] = (old + 8, p4)

    # Old 074-083 -> New 084-093 (Phase 5)
    for old in range(74, 84):
        renumber_map[old] = (old + 10, p5)

    # Step 4: Move existing days from temp to new locations with new numbers
    for day_num, phase_name, dir_name, old_phase_path in existing_days:
        new_day_num, new_phase_path = renumber_map[day_num]
        topic = dir_name.split("_", 2)[2]
        new_dir_name = f"Day_{new_day_num:03d}_{topic}"

        src = os.path.join(temp_dir, dir_name)
        dst = os.path.join(new_phase_path, new_dir_name)
        shutil.move(src, dst)

        # Rename .md file inside if needed
        for f in os.listdir(dst):
            if f.endswith(".md"):
                # File name stays the same (topic-based), no rename needed
                break

    print("Renumbered all existing days")

    # Step 5: Create new day placeholders
    new_days = [
        (p0, 1, "ai_engineering_career_map", "The AI Engineering Career Map"),
        (p1, 25, "testing_llm_applications", "Testing LLM Applications"),
        (p1, 26, "capstone_data_extraction_pipeline", "Capstone: Build a Structured Data Extraction Pipeline"),
        (p2, 39, "cost_engineering_for_llms", "Cost Engineering for LLMs"),
        (p2, 40, "capstone_rag_chatbot", "Capstone: Build a RAG Chatbot"),
        (p3, 54, "debugging_ai_agents", "Debugging AI Agents"),
        (p3, 55, "capstone_autonomous_research_agent", "Capstone: Build an Autonomous Research Agent"),
        (p3, 56, "career_checkpoint", "Career Checkpoint: Mid-Journey Review"),
        (p4, 82, "production_hardening", "Production Hardening for AI Systems"),
        (p4, 83, "capstone_multi_agent_pipeline", "Capstone: Multi-Agent Content Pipeline with Human Review"),
        (p5, 94, "model_context_protocol", "Model Context Protocol (MCP)"),
        (p5, 95, "claude_agent_sdk", "Claude Agent SDK"),
        (p5, 96, "prompt_engineering_discipline", "Prompt Engineering as a Discipline"),
        (p5, 97, "capstone_deploy_to_production", "Capstone: Deploy an AI Agent to Production"),
        (p6, 98, "ai_engineering_interview_prep", "AI Engineering Interview Prep"),
        (p6, 99, "building_your_portfolio", "Building Your AI Portfolio"),
        (p6, 100, "career_launch", "Your 100-Day Journey is Complete — What's Next"),
    ]

    for phase_path, day_num, topic, title in new_days:
        create_placeholder_day(phase_path, day_num, topic, title)
        print(f"  Created Day {day_num:03d}: {title}")

    # Cleanup temp
    shutil.rmtree(temp_dir)

    # Step 6: Verify
    print("\n=== Final Structure ===")
    all_phases = {**NEW_PHASES, **PHASES}
    total = 0
    for name in sorted(all_phases.keys()):
        path = all_phases[name]
        days = sorted([d for d in os.listdir(path) if d.startswith("Day_")])
        total += len(days)
        if days:
            first = days[0].split("_")[1]
            last = days[-1].split("_")[1]
            print(f"  {name}: {len(days)} days (Day {first}-{last})")
        else:
            print(f"  {name}: 0 days")
    print(f"  TOTAL: {total} days")


if __name__ == "__main__":
    main()
