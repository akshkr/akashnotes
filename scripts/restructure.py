#!/usr/bin/env python3
"""Restructure the LLM curriculum from Month/Week into 83-day challenge format."""

import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

M1 = "Month_1_LLM_Interface_Python_Integration"
M2 = "Month_2_External_Knowledge_Tool_Calling"
M3 = "Month_3_Single_Agent_Architectures"
M4 = "Month_4_Multi_Agent_Systems"
M5 = "Month_5_Evaluation_Observability_Security"
M6 = "Month_6_Production_Deployment"


def src(month, week, filename):
    return os.path.join(BASE, month, week, filename)


def split_file_at_heading(filepath, heading):
    """Split a markdown file at the given ## heading. Returns (part1, part2)."""
    with open(filepath, "r") as f:
        content = f.read()

    idx = content.find(f"\n{heading}")
    if idx == -1:
        # Try with ## prefix
        idx = content.find(f"\n## {heading}")
    if idx == -1:
        raise ValueError(f"Heading '{heading}' not found in {filepath}")

    part1 = content[:idx].rstrip() + "\n"
    part2 = content[idx:].lstrip("\n")
    return part1, part2


def merge_files(filepath1, filepath2):
    """Merge two markdown files with a separator."""
    with open(filepath1, "r") as f:
        content1 = f.read()
    with open(filepath2, "r") as f:
        content2 = f.read()
    return content1.rstrip() + "\n\n---\n\n" + content2.lstrip()


def write_day(phase_dir, day_num, day_name, content):
    """Create a day directory and write content."""
    day_dir = os.path.join(phase_dir, f"Day_{day_num:03d}_{day_name}")
    os.makedirs(day_dir, exist_ok=True)
    filepath = os.path.join(day_dir, f"{day_name}.md")
    with open(filepath, "w") as f:
        f.write(content)
    return day_dir


def copy_day(phase_dir, day_num, day_name, source_path):
    """Copy a standalone file into a day directory."""
    with open(source_path, "r") as f:
        content = f.read()
    return write_day(phase_dir, day_num, day_name, content)


def split_day(phase_dir, day_num1, name1, day_num2, name2, source_path, heading):
    """Split a file into two days at the given heading."""
    part1, part2 = split_file_at_heading(source_path, heading)
    d1 = write_day(phase_dir, day_num1, name1, part1)
    d2 = write_day(phase_dir, day_num2, name2, part2)
    return d1, d2


def main():
    # Create phase directories
    phases = {
        "Phase_1_LLM_Foundations": os.path.join(BASE, "Phase_1_LLM_Foundations"),
        "Phase_2_External_Knowledge": os.path.join(BASE, "Phase_2_External_Knowledge"),
        "Phase_3_Single_Agent": os.path.join(BASE, "Phase_3_Single_Agent"),
        "Phase_4_MultiAgent_Eval_Security": os.path.join(BASE, "Phase_4_MultiAgent_Eval_Security"),
        "Phase_5_Production": os.path.join(BASE, "Phase_5_Production"),
    }
    for p in phases.values():
        os.makedirs(p, exist_ok=True)

    p1 = phases["Phase_1_LLM_Foundations"]
    p2 = phases["Phase_2_External_Knowledge"]
    p3 = phases["Phase_3_Single_Agent"]
    p4 = phases["Phase_4_MultiAgent_Eval_Security"]
    p5 = phases["Phase_5_Production"]

    # ── Phase 1: LLM Foundations (Days 001-023) ──
    w1 = f"{M1}/Week_1_Mental_Models_for_LLMs"
    w2 = f"{M1}/Week_2_Advanced_Prompting_Techniques"
    w3 = f"{M1}/Week_3_Python_API_Mastery"
    w4 = f"{M1}/Week_4_Structured_Output_Data_Parsing"

    # Day 001: standalone
    copy_day(p1, 1, "transformer_intuition", src(M1, "Week_1_Mental_Models_for_LLMs", "01_transformer_intuition.md"))

    # Day 002-003: tokenization split
    split_day(p1, 2, "tokenization_part1", 3, "tokenization_part2",
              src(M1, "Week_1_Mental_Models_for_LLMs", "02_tokenization.md"),
              "## Calculating Token Costs")

    # Day 004-005: temperature_and_sampling split
    split_day(p1, 4, "temperature_and_sampling_part1", 5, "temperature_and_sampling_part2",
              src(M1, "Week_1_Mental_Models_for_LLMs", "03_temperature_and_sampling.md"),
              "## Temperature vs Top-P: When to Use Which?")

    # Day 006-007: zero_shot_vs_few_shot split
    split_day(p1, 6, "zero_shot_vs_few_shot_part1", 7, "zero_shot_vs_few_shot_part2",
              src(M1, "Week_2_Advanced_Prompting_Techniques", "01_zero_shot_vs_few_shot.md"),
              "## Side-by-Side Comparison")

    # Day 008-009: chain_of_thought split
    split_day(p1, 8, "chain_of_thought_part1", 9, "chain_of_thought_part2",
              src(M1, "Week_2_Advanced_Prompting_Techniques", "02_chain_of_thought.md"),
              "## When CoT Helps Most")

    # Day 010-011: system_vs_user_prompts split
    split_day(p1, 10, "system_vs_user_prompts_part1", 11, "system_vs_user_prompts_part2",
              src(M1, "Week_2_Advanced_Prompting_Techniques", "03_system_vs_user_prompts.md"),
              "## System Prompt vs User Prompt: Practical Decisions")

    # Day 012-013: openai_anthropic_sdks split
    split_day(p1, 12, "openai_anthropic_sdks_part1", 13, "openai_anthropic_sdks_part2",
              src(M1, "Week_3_Python_API_Mastery", "01_openai_anthropic_sdks.md"),
              "## Key Differences: OpenAI vs Anthropic")

    # Day 014-015: async_llm_calls split
    split_day(p1, 14, "async_llm_calls_part1", 15, "async_llm_calls_part2",
              src(M1, "Week_3_Python_API_Mastery", "02_async_llm_calls.md"),
              "## Progress Tracking")

    # Day 016-017: streaming_responses split
    split_day(p1, 16, "streaming_responses_part1", 17, "streaming_responses_part2",
              src(M1, "Week_3_Python_API_Mastery", "03_streaming_responses.md"),
              "## Building a Streaming Chat Interface")

    # Day 018-019: pydantic_schemas split
    split_day(p1, 18, "pydantic_schemas_part1", 19, "pydantic_schemas_part2",
              src(M1, "Week_4_Structured_Output_Data_Parsing", "01_pydantic_schemas.md"),
              "## Using Pydantic with LLMs")

    # Day 020-021: forcing_json_output split
    split_day(p1, 20, "forcing_json_output_part1", 21, "forcing_json_output_part2",
              src(M1, "Week_4_Structured_Output_Data_Parsing", "02_forcing_json_output.md"),
              "## Technique 5: Using json-repair Library")

    # Day 022-023: retry_loops split
    split_day(p1, 22, "retry_loops_part1", 23, "retry_loops_part2",
              src(M1, "Week_4_Structured_Output_Data_Parsing", "03_retry_loops.md"),
              "## Exponential Backoff for Rate Limits")

    # ── Phase 2: External Knowledge (Days 024-035) ──
    copy_day(p2, 24, "what_are_embeddings",
             src(M2, "Week_1_Embeddings_Vector_Math", "01_what_are_embeddings.md"))
    copy_day(p2, 25, "cosine_euclidean_similarity",
             src(M2, "Week_1_Embeddings_Vector_Math", "02_cosine_euclidean_similarity.md"))
    copy_day(p2, 26, "generating_embeddings_api",
             src(M2, "Week_1_Embeddings_Vector_Math", "03_generating_embeddings_api.md"))
    copy_day(p2, 27, "chromadb_faiss_setup",
             src(M2, "Week_2_Vector_Databases", "01_chromadb_faiss_setup.md"))
    copy_day(p2, 28, "indexing_querying_updating",
             src(M2, "Week_2_Vector_Databases", "02_indexing_querying_updating.md"))
    copy_day(p2, 29, "document_parsing",
             src(M2, "Week_3_RAG", "01_document_parsing.md"))
    copy_day(p2, 30, "text_chunking",
             src(M2, "Week_3_RAG", "02_text_chunking.md"))
    copy_day(p2, 31, "context_injection",
             src(M2, "Week_3_RAG", "03_context_injection.md"))
    copy_day(p2, 32, "function_calling_basics",
             src(M2, "Week_4_Tool_Calling", "01_function_calling_basics.md"))
    copy_day(p2, 33, "json_schema_generation",
             src(M2, "Week_4_Tool_Calling", "02_json_schema_generation.md"))

    # Day 034-035: tool_execution_handling split
    split_day(p2, 34, "tool_execution_handling_part1", 35, "tool_execution_handling_part2",
              src(M2, "Week_4_Tool_Calling", "03_tool_execution_handling.md"),
              "## Handling Multiple Tool Calls")

    # ── Phase 3: Single Agent (Days 036-048) ──
    copy_day(p3, 36, "react_loop",
             src(M3, "Week_1_From_Scratch_Agent", "01_react_loop.md"))
    copy_day(p3, 37, "conversation_history",
             src(M3, "Week_1_From_Scratch_Agent", "02_conversation_history.md"))

    # Day 038-039: max_iterations split
    split_day(p3, 38, "max_iterations_part1", 39, "max_iterations_part2",
              src(M3, "Week_1_From_Scratch_Agent", "03_max_iterations.md"),
              "## Graceful Termination")

    copy_day(p3, 40, "langchain_basics",
             src(M3, "Week_2_LangChain_LlamaIndex", "01_langchain_basics.md"))

    # Day 041: merge llamaindex_basics + framework_comparison
    merged = merge_files(
        src(M3, "Week_2_LangChain_LlamaIndex", "02_llamaindex_basics.md"),
        src(M3, "Week_2_LangChain_LlamaIndex", "03_framework_comparison.md"))
    write_day(p3, 41, "llamaindex_and_framework_comparison", merged)

    copy_day(p3, 42, "state_machines",
             src(M3, "Week_3_LangGraph", "01_state_machines.md"))
    copy_day(p3, 43, "nodes_and_edges",
             src(M3, "Week_3_LangGraph", "02_nodes_and_edges.md"))
    copy_day(p3, 44, "compiling_graphs",
             src(M3, "Week_3_LangGraph", "03_compiling_graphs.md"))

    # Day 045-046: checkpoints_persistence split
    split_day(p3, 45, "checkpoints_persistence_part1", 46, "checkpoints_persistence_part2",
              src(M3, "Week_4_Memory_Persistence", "01_checkpoints_persistence.md"),
              "## Database Persistence")

    copy_day(p3, 47, "time_travel_debugging",
             src(M3, "Week_4_Memory_Persistence", "02_time_travel_debugging.md"))
    copy_day(p3, 48, "database_storage",
             src(M3, "Week_4_Memory_Persistence", "03_database_storage.md"))

    # ── Phase 4: MultiAgent + Eval + Security (Days 049-073) ──
    copy_day(p4, 49, "agent_topologies",
             src(M4, "Week_1_Multi_Agent_Topologies", "01_agent_topologies.md"))
    copy_day(p4, 50, "supervisor_worker",
             src(M4, "Week_1_Multi_Agent_Topologies", "02_supervisor_worker.md"))
    copy_day(p4, 51, "adversarial_debate",
             src(M4, "Week_1_Multi_Agent_Topologies", "03_adversarial_debate.md"))
    copy_day(p4, 52, "crewai_basics",
             src(M4, "Week_2_CrewAI", "01_crewai_basics.md"))
    copy_day(p4, 53, "tasks_definition",
             src(M4, "Week_2_CrewAI", "02_tasks_definition.md"))
    copy_day(p4, 54, "sequential_parallel",
             src(M4, "Week_2_CrewAI", "03_sequential_parallel.md"))
    copy_day(p4, 55, "autogen_basics",
             src(M4, "Week_3_AutoGen", "01_autogen_basics.md"))
    copy_day(p4, 56, "user_proxy_agents",
             src(M4, "Week_3_AutoGen", "02_user_proxy_agents.md"))
    copy_day(p4, 57, "code_execution_environments",
             src(M4, "Week_3_AutoGen", "03_code_execution_environments.md"))

    # Day 058-059: hitl_patterns split
    split_day(p4, 58, "hitl_patterns_part1", 59, "hitl_patterns_part2",
              src(M4, "Week_4_Human_in_Loop", "01_hitl_patterns.md"),
              "## Multi-Stage Approval Pipeline")

    copy_day(p4, 60, "breakpoints_design",
             src(M4, "Week_4_Human_in_Loop", "02_breakpoints_design.md"))
    copy_day(p4, 61, "injecting_feedback",
             src(M4, "Week_4_Human_in_Loop", "03_injecting_feedback.md"))

    # Month 5 content
    copy_day(p4, 62, "langsmith_phoenix",
             src(M5, "Week_1_Observability_Tracing", "01_langsmith_phoenix.md"))
    copy_day(p4, 63, "token_latency_visualization",
             src(M5, "Week_1_Observability_Tracing", "02_token_latency_visualization.md"))

    # Day 064-065: llm_as_judge split
    split_day(p4, 64, "llm_as_judge_part1", 65, "llm_as_judge_part2",
              src(M5, "Week_2_Automated_Evaluation", "01_llm_as_judge.md"),
              "## Agent Trajectory Evaluation")

    copy_day(p4, 66, "ragas_evaluation",
             src(M5, "Week_2_Automated_Evaluation", "02_ragas_evaluation.md"))
    copy_day(p4, 67, "trajectory_evaluation",
             src(M5, "Week_2_Automated_Evaluation", "03_trajectory_evaluation.md"))
    copy_day(p4, 68, "prompt_injection",
             src(M5, "Week_3_Security_Guardrails", "01_prompt_injection.md"))
    copy_day(p4, 69, "output_sanitization",
             src(M5, "Week_3_Security_Guardrails", "02_output_sanitization.md"))
    copy_day(p4, 70, "nemo_guardrails",
             src(M5, "Week_3_Security_Guardrails", "03_nemo_guardrails.md"))

    # Day 071-072: docker_sandboxing split
    split_day(p4, 71, "docker_sandboxing_part1", 72, "docker_sandboxing_part2",
              src(M5, "Week_4_Safe_Sandboxing", "01_docker_sandboxing.md"),
              "## API Key Security")

    copy_day(p4, 73, "api_key_security",
             src(M5, "Week_4_Safe_Sandboxing", "02_api_key_security.md"))

    # ── Phase 5: Production (Days 074-083) ──
    copy_day(p5, 74, "ollama_local_models",
             src(M6, "Week_1_Local_Models", "01_ollama_local_models.md"))

    # Day 075: merge quantization + swapping_local_models
    merged = merge_files(
        src(M6, "Week_1_Local_Models", "02_quantization.md"),
        src(M6, "Week_1_Local_Models", "03_swapping_local_models.md"))
    write_day(p5, 75, "quantization_and_swapping_models", merged)

    copy_day(p5, 76, "fastapi_agents",
             src(M6, "Week_2_Agent_APIs", "01_fastapi_agents.md"))
    copy_day(p5, 77, "async_task_handling",
             src(M6, "Week_2_Agent_APIs", "02_async_task_handling.md"))
    copy_day(p5, 78, "websockets_streaming",
             src(M6, "Week_2_Agent_APIs", "03_websockets_streaming.md"))
    copy_day(p5, 79, "streamlit_gradio",
             src(M6, "Week_3_Agent_UIs", "01_streamlit_gradio.md"))
    copy_day(p5, 80, "displaying_content_ui",
             src(M6, "Week_3_Agent_UIs", "02_displaying_content_ui.md"))
    copy_day(p5, 81, "docker_deployment",
             src(M6, "Week_4_Cloud_Deployment", "01_docker_deployment.md"))
    copy_day(p5, 82, "rate_limits_backoffs",
             src(M6, "Week_4_Cloud_Deployment", "02_rate_limits_backoffs.md"))
    copy_day(p5, 83, "cloud_deployment",
             src(M6, "Week_4_Cloud_Deployment", "03_cloud_deployment.md"))

    print("Done! Created 83 days across 5 phases.")

    # Verify
    total_days = 0
    for phase_name, phase_path in sorted(phases.items()):
        days = [d for d in os.listdir(phase_path) if d.startswith("Day_")]
        total_days += len(days)
        print(f"  {phase_name}: {len(days)} days")
    print(f"  Total: {total_days} days")


if __name__ == "__main__":
    main()
