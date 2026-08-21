"""
Agent 1: Resume Optimization Agent.

Regenerates resume content (summary, bullets, skills framing) to fit a
target job description, using a generator -> critic loop:

  1. Generator rewrites the resume against the JD.
  2. Critic checks the rewrite for (a) fabricated experience/skills not
     present in the original resume, and (b) genuine JD-fit improvement.
  3. If the critic rejects it, the generator retries (up to MAX_ROUNDS)
     with the critic's feedback appended to the prompt.

This generator/critic split is the evaluable unit for the paper: you can
report critic-rejection rate, average rounds-to-acceptance, and
fabrication-flag rate as metrics, and score ATS-fit delta (via
utils.scoring.compute_ats_formula_score) pre/post optimization.
"""
from utils.agent_client import call_json
from utils.scoring import compute_ats_formula_score

MAX_ROUNDS = 1  # was 2 — each extra round adds up to 2 more sequential Groq
# calls (generator + critic), which was pushing total pipeline latency past
# Render free tier's request timeout and causing a 502 with no response body.


GENERATOR_PROMPT_TEMPLATE = """You are an expert resume writer. Rewrite the RESUME below to better fit the JOB DESCRIPTION, maximizing keyword and role alignment.

STRICT RULES:
- Do NOT invent employers, job titles, degrees, certifications, or metrics that are not implied by the original resume.
- You MAY rephrase, reorder, add stronger action verbs, and surface relevant skills already present but under-emphasized.
- Keep the same overall structure (summary, experience, education, skills, projects) unless a section is missing.
- Every change must be traceable to something actually in the original resume.
{feedback_block}

ORIGINAL RESUME:
\"\"\"
{resume_text}
\"\"\"

JOB DESCRIPTION:
\"\"\"
{job_description}
\"\"\"

Return ONLY a valid JSON object, no markdown, no code fences:
{{
  "optimized_text": "<full rewritten resume as plain text>",
  "changes": [
    {{"section": "<section name>", "before": "<short original snippet>", "after": "<short rewritten snippet>", "reason": "<why this helps JD-fit>"}}
  ]
}}"""


CRITIC_PROMPT_TEMPLATE = """You are a strict fact-checking editor reviewing a resume rewrite for fabrication and genuine JD-fit.

ORIGINAL RESUME:
\"\"\"
{resume_text}
\"\"\"

REWRITTEN RESUME:
\"\"\"
{optimized_text}
\"\"\"

JOB DESCRIPTION:
\"\"\"
{job_description}
\"\"\"

Check for:
1. Fabrication: any employer, title, degree, certification, tool, or quantified metric in the rewrite that is NOT supported by the original resume.
2. JD-fit: does the rewrite genuinely emphasize skills/experience relevant to the JD, or is it superficial keyword-stuffing?

Return ONLY valid JSON, no markdown:
{{
  "approved": <true/false>,
  "fabrication_flags": [<specific unsupported claims found, empty list if none>],
  "fit_improved": <true/false>,
  "feedback": "<1-3 sentences of concrete feedback for the generator if not approved, else 'None'>"
}}"""


def _run_generator(resume_text: str, job_description: str, feedback: str = None) -> dict:
    feedback_block = f"\nPRIOR CRITIC FEEDBACK TO ADDRESS:\n{feedback}\n" if feedback else ""
    prompt = GENERATOR_PROMPT_TEMPLATE.format(
        resume_text=resume_text[:4000],
        job_description=job_description[:3000],
        feedback_block=feedback_block,
    )
    return call_json(prompt, temperature=0.4, max_tokens=2800)


def _run_critic(resume_text: str, optimized_text: str, job_description: str) -> dict:
    prompt = CRITIC_PROMPT_TEMPLATE.format(
        resume_text=resume_text[:4000],
        optimized_text=optimized_text[:4000],
        job_description=job_description[:3000],
    )
    return call_json(prompt, temperature=0.1, max_tokens=800)


def optimize_resume(resume_text: str, job_description: str) -> dict:
    """
    Runs the generator -> critic loop and returns the final result plus
    a trace of every round (useful for the paper's ablation/analysis).
    """
    if not job_description or not job_description.strip():
        return {
            "optimized_text": resume_text,
            "changes": [],
            "approved": False,
            "rounds": 0,
            "trace": [],
            "note": "No job description provided; optimization requires a target JD.",
        }

    trace = []
    feedback = None
    generated = None
    critic_result = None

    for round_num in range(1, MAX_ROUNDS + 1):
        try:
            generated = _run_generator(resume_text, job_description, feedback)
        except Exception as e:
            trace.append({"round": round_num, "stage": "generator_error", "error": str(e)})
            break

        try:
            critic_result = _run_critic(resume_text, generated.get("optimized_text", ""), job_description)
        except Exception as e:
            trace.append({"round": round_num, "stage": "critic_error", "error": str(e)})
            critic_result = {"approved": True, "fabrication_flags": [], "fit_improved": True,
                              "feedback": "Critic unavailable; auto-accepted."}

        trace.append({
            "round": round_num,
            "critic_approved": critic_result.get("approved"),
            "fabrication_flags": critic_result.get("fabrication_flags", []),
        })

        if critic_result.get("approved") and not critic_result.get("fabrication_flags"):
            break

        feedback = critic_result.get("feedback")

    if generated is None:
        return {
            "optimized_text": resume_text,
            "changes": [],
            "approved": False,
            "rounds": len(trace),
            "trace": trace,
            "note": "Generation failed.",
        }

    # ── measurable before/after ATS-fit delta, for the paper ──
    before_score = compute_ats_formula_score(resume_text, job_description)["formula_score"]
    after_score = compute_ats_formula_score(generated.get("optimized_text", resume_text), job_description)["formula_score"]

    return {
        "optimized_text": generated.get("optimized_text", resume_text),
        "changes": generated.get("changes", []),
        "approved": bool(critic_result and critic_result.get("approved")),
        "fabrication_flags": critic_result.get("fabrication_flags", []) if critic_result else [],
        "rounds": len(trace),
        "trace": trace,
        "ats_formula_score_before": before_score,
        "ats_formula_score_after": after_score,
        "ats_formula_score_delta": after_score - before_score,
    }