"""
Agent 2b: Skill Gap + Learning Roadmap Agent.

Consumes the output of the Job Market Intelligence Agent
(in-demand skills for the matched role) and diffs it against skills
detected in the candidate's resume, then asks the LLM to turn the gap
into a prioritized, time-boxed learning roadmap.

The gap computation itself is deterministic (simple containment check,
mirrors the transparent-formula philosophy of utils/scoring.py) so
`coverage_percent` is a reproducible metric you can report directly in
the paper. Only the roadmap *narrative* (phases/resources/ordering) is
LLM-generated.
"""
import re
from utils.agent_client import call_json


def _skill_present_in_resume(skill_name: str, resume_text: str) -> bool:
    """
    Deterministic containment check. Handles multi-token skill names like
    "Docker / Kubernetes" or "Python / Java / Go" by checking if ANY
    slash-separated alternative appears in the resume.
    """
    resume_lower = resume_text.lower()
    alternatives = [alt.strip() for alt in skill_name.split("/")]
    for alt in alternatives:
        # strip parenthetical examples e.g. "Cloud (AWS/Azure/GCP)" -> also check inner terms
        base = re.sub(r"\(.*?\)", "", alt).strip()
        inner = re.findall(r"\((.*?)\)", alt)
        terms = [base] + [t.strip() for group in inner for t in group.split("/")]
        for term in terms:
            if term and re.search(re.escape(term.lower()), resume_lower):
                return True
    return False


def compute_skill_gap(resume_text: str, in_demand_skills: list) -> dict:
    covered, missing = [], []
    for skill in in_demand_skills:
        if _skill_present_in_resume(skill["name"], resume_text):
            covered.append(skill)
        else:
            missing.append(skill)

    total = len(in_demand_skills) or 1
    coverage_percent = round(100 * len(covered) / total, 1)

    return {
        "covered_skills": covered,
        "missing_skills": sorted(missing, key=lambda s: s["demand_score"], reverse=True),
        "coverage_percent": coverage_percent,
    }


ROADMAP_PROMPT_TEMPLATE = """You are a career development coach. A candidate targeting the role "{role}" has these skill gaps, ordered by market demand (highest first):

{missing_skills_block}

They already have these skills (do not repeat these in the roadmap):
{covered_skills_block}

Create a prioritized, time-boxed learning roadmap that closes the highest-demand gaps first. Assume the candidate can commit roughly 8-10 hours/week.

Return ONLY valid JSON, no markdown:
{{
  "total_duration_weeks": <integer>,
  "phases": [
    {{
      "title": "<phase name, e.g. 'Weeks 1-3: Foundation'>",
      "duration_weeks": <integer>,
      "skills": [<skill names covered in this phase>],
      "milestone": "<a concrete, verifiable milestone for this phase, e.g. 'Ship a small project using X'>",
      "resource_suggestions": [<2-3 specific resource TYPES, e.g. 'official Kubernetes docs + a guided project', not fake URLs>]
    }}
  ],
  "summary": "<2-3 sentence overview of the roadmap strategy and why this ordering was chosen>"
}}"""


def generate_roadmap(role: str, skill_gap: dict) -> dict:
    missing = skill_gap.get("missing_skills", [])
    covered = skill_gap.get("covered_skills", [])

    if not missing:
        return {
            "total_duration_weeks": 0,
            "phases": [],
            "summary": "No significant skill gaps detected against this role's in-demand skill set.",
        }

    missing_block = "\n".join(f"- {s['name']} (demand: {s['demand_score']}/100, category: {s['category']})" for s in missing)
    covered_block = "\n".join(f"- {s['name']}" for s in covered) or "(none detected)"

    prompt = ROADMAP_PROMPT_TEMPLATE.format(
        role=role,
        missing_skills_block=missing_block,
        covered_skills_block=covered_block,
    )

    try:
        return call_json(prompt, temperature=0.3, max_tokens=1800)
    except Exception as e:
        return {
            "total_duration_weeks": None,
            "phases": [],
            "summary": f"Roadmap generation failed: {e}",
        }


def run_gap_and_roadmap(resume_text: str, matched_role: str, in_demand_skills: list) -> dict:
    """Convenience wrapper combining gap computation + roadmap generation."""
    skill_gap = compute_skill_gap(resume_text, in_demand_skills)
    roadmap = generate_roadmap(matched_role, skill_gap)
    return {"skill_gap": skill_gap, "roadmap": roadmap}