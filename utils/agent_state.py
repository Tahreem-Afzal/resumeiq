"""
Shared state schema passed between nodes in the LangGraph pipeline.

Each agent reads the fields it needs and writes only the field(s) it
owns, so nodes can (in principle) run in parallel without clobbering
each other's output — LangGraph merges dict updates by key.
"""
from typing import TypedDict, List, Dict, Optional


class AgentState(TypedDict, total=False):
    # ── inputs ──
    resume_text: str
    job_description: str
    analysis_report: dict          # output of utils.analyzer.analyze_resume, if available

    # ── agent 1: resume optimization ──
    optimized_resume: dict         # {"optimized_text": str, "changes": [...], "critic_notes": [...]}

    # ── agent 2a: job market intelligence ──
    market_intel: dict             # {"matched_role": str, "in_demand_skills": [...]}

    # ── agent 2b: skill gap + learning roadmap ──
    skill_gap: dict                # {"covered_skills": [...], "missing_skills": [...], "coverage_percent": float}
    roadmap: dict                  # {"phases": [{"title", "duration", "skills", "resources"}]}

    # ── agent 3: mock interview (used outside the linear graph, session-based) ──
    interview_transcript: List[Dict]
    interview_evaluation: dict

    # ── bookkeeping ──
    errors: List[str]