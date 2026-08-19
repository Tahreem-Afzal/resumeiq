"""
Agent 2a: Job Market Intelligence Agent.

Matches the candidate's target role (from the job description, or from
the resume itself if no JD is given) against a curated, static
skills-demand taxonomy (data/skills_taxonomy.json), and returns the
in-demand skills for that role.

Static-dataset design choice (vs. live scraping) is deliberate: it keeps
results reproducible run-to-run, which matters for a research paper's
evaluation section. Swap `_load_taxonomy` for a live-search-backed
implementation later without changing the return contract.
"""
import os
import json
import re

from utils.agent_client import call_json

TAXONOMY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "skills_taxonomy.json"
)

_taxonomy_cache = None


def _load_taxonomy() -> dict:
    global _taxonomy_cache
    if _taxonomy_cache is None:
        with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
            _taxonomy_cache = json.load(f)
    return _taxonomy_cache


def _keyword_match_role(text: str, roles: dict) -> str:
    """Fast, deterministic fallback: score each role by alias occurrence in text."""
    text_lower = text.lower()
    best_role, best_score = None, 0
    for role_name, role_data in roles.items():
        score = 0
        for alias in role_data.get("aliases", []) + [role_name.lower()]:
            if re.search(re.escape(alias.lower()), text_lower):
                score += 1
        if score > best_score:
            best_role, best_score = role_name, score
    return best_role


def _llm_match_role(text: str, role_names: list) -> str:
    """LLM fallback when keyword matching is inconclusive (e.g. no exact alias hit)."""
    prompt = f"""Given this resume/job-description text, pick the SINGLE best-matching role from this exact list (return the exact string, nothing else):

{json.dumps(role_names)}

TEXT:
\"\"\"
{text[:2500]}
\"\"\"

Return ONLY valid JSON: {{"role": "<exact role name from the list>"}}"""
    try:
        result = call_json(prompt, temperature=0.0, max_tokens=100)
        role = result.get("role")
        return role if role in role_names else role_names[0]
    except Exception:
        return role_names[0]


def get_market_intel(resume_text: str, job_description: str = "") -> dict:
    """
    Returns: {
      "matched_role": str,
      "match_method": "keyword" | "llm_fallback",
      "in_demand_skills": [{"name", "demand_score", "category"}, ...]  # sorted by demand_score desc
    }
    """
    taxonomy = _load_taxonomy()
    roles = taxonomy["roles"]
    role_names = list(roles.keys())

    match_text = job_description.strip() if job_description.strip() else resume_text
    matched_role = _keyword_match_role(match_text, roles)
    match_method = "keyword"

    if not matched_role:
        matched_role = _llm_match_role(match_text, role_names)
        match_method = "llm_fallback"

    skills = sorted(roles[matched_role]["skills"], key=lambda s: s["demand_score"], reverse=True)

    return {
        "matched_role": matched_role,
        "match_method": match_method,
        "in_demand_skills": skills,
        "taxonomy_last_updated": taxonomy.get("_meta", {}).get("last_updated"),
    }