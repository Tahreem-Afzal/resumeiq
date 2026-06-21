import os
import json
from groq import Groq
from dotenv import load_dotenv

from utils.scoring import compute_ats_formula_score, apply_llm_adjustment
from utils import database

load_dotenv()

MODEL = "llama-3.3-70b-versatile"


def get_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to your .env file (local) or environment variables (Render).")
    return Groq(api_key=api_key, timeout=30.0)


def analyze_resume(resume_text: str, job_description: str = "", save_to_history: bool = True) -> dict:
    client = get_client()

    # ── Deterministic formula score (computed BEFORE the LLM call) ──
    formula_result = compute_ats_formula_score(resume_text, job_description)
    formula_score = formula_result["formula_score"]

    jd_block = ""
    jd_instructions = ""
    if job_description:
        jd_block = f"""
JOB DESCRIPTION TO MATCH AGAINST:
\"\"\"
{job_description[:3000]}
\"\"\"
"""
        jd_instructions = """
Since a job description WAS provided:
- Set "has_jd" to true
- Fill "role_name" with a short label for the role (e.g. "Frontend Developer Internship")
- Fill "keyword_categories" with 3-6 relevant skill/domain categories drawn from the JD (e.g. "AI / Machine Learning", "Cloud / DevOps", "Communication") and a 0-100 match percentage for each based on resume evidence
- Fill "verdict" with a clear apply/don't-apply recommendation and reasoning tied to the JD
- Fill "deadline_note" with null (no deadline known) unless the JD text mentions one
"""
    else:
        jd_instructions = """
Since NO job description was provided:
- Set "has_jd" to false
- Set "role_name" to null
- Still fill "keyword_categories" but base categories on general strong career directions implied by the resume itself (e.g. if it's an AI resume: "AI / Machine Learning", "Data Science", "Software Engineering") with an estimated 0-100 strength score for each based on resume evidence
- Fill "verdict" with general career positioning advice instead of an apply/don't-apply call
- Set "deadline_note" to null
"""

    prompt = f"""You are an expert ATS resume analyzer and career coach. Analyze the resume below and return ONLY a valid JSON object — no markdown, no explanation, no extra text, no code fences.

A DETERMINISTIC SCORING FORMULA has already computed a base ATS score of {formula_score}/100 for this resume, based on keyword overlap, section completeness, and formatting heuristics. You may adjust this by AT MOST +/-5 points if you have a clear qualitative reason (e.g. exceptional achievements, severe red flags not captured by the formula). Most of the time, no adjustment or a small one is appropriate.

RESUME:
\"\"\"
{resume_text[:4000]}
\"\"\"
{jd_block}
{jd_instructions}

Return this exact JSON structure:
{{
  "has_jd": <true/false>,
  "role_name": <string or null>,
  "overall_score": <integer 0-100>,
  "ats_score_llm_adjustment": <integer -5 to 5, how much you are adjusting the formula score of {formula_score}>,
  "ats_score_adjustment_reason": "<1 sentence explaining the adjustment, or 'No adjustment needed' if 0>",
  "jd_match_percent": <integer 0-100, or a general "career strength" percent if no JD>,
  "ats_format_ok": <true/false>,
  "ats_format_note": "<short phrase like 'Strong pass' or 'Minor issues'>",
  "apply_recommendation": "<'yes' or 'maybe' or 'no'>",
  "deadline_note": <string or null>,
  "sections_detected": {{
    "contact": <true/false>, "summary": <true/false>, "experience": <true/false>,
    "education": <true/false>, "skills": <true/false>, "projects": <true/false>
  }},
  "section_scores": {{
    "contact": <0-100>, "experience": <0-100>, "skills": <0-100>,
    "education": <0-100>, "formatting": <0-100>
  }},
  "keyword_categories": [
    {{"name": "<category name>", "match_percent": <0-100>}}
  ],
  "keywords_found": [<5-10 specific skills/keywords genuinely present in the resume>],
  "keywords_weak": [<0-3 keywords present but underrepresented>],
  "keywords_missing": [<up to 8 important missing keywords>],
  "ats_format_checks": [
    {{"status": "ok", "text": "<a specific formatting/structure strength found>"}},
    {{"status": "warn", "text": "<a specific formatting/structure concern found>"}},
    {{"status": "bad", "text": "<a specific formatting/structure problem found, omit if none>"}}
  ],
  "verdict_title": "<short bold headline like 'Yes — apply now' or 'Strong fit for X roles'>",
  "verdict_text": "<2-4 sentence reasoning for the verdict, referencing specific resume content>",
  "strengths": [<3-4 specific strength strings>],
  "improvements": [<4-5 specific actionable improvement strings>],
  "tips": [
    {{"title": "<short tip title>", "body": "<1-2 sentence actionable tip referencing specific resume content>"}}
  ],
  "weak_bullets": [<up to 3 weak bullet point examples from resume>],
  "rewritten_bullets": [<rewritten stronger versions of those bullets, same order>],
  "interview_questions": [<exactly 10 likely interview questions based on this resume{', tailored to the job description' if job_description else ''}>],
  "grammar_issues": [<up to 3 grammar or language issues found, or empty list>],
  "summary_feedback": "<2-3 sentence overall verdict on this resume>"
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "overall_score": 0,
            "ats_score": formula_score,
            "error": "AI returned malformed response. Please try again.",
            "summary_feedback": raw[:500]
        }
        result["scoring_breakdown"] = formula_result
        return result

    # ── Apply bounded LLM adjustment to the formula score ──
    llm_adjustment = result.get("ats_score_llm_adjustment", 0) or 0
    llm_reason = result.get("ats_score_adjustment_reason", "No adjustment needed")
    adjustment_result = apply_llm_adjustment(formula_score, llm_adjustment, llm_reason)

    result["ats_score"] = adjustment_result["final_score"]
    result["scoring_breakdown"] = {
        "formula_score": formula_result["formula_score"],
        "llm_adjustment": adjustment_result["llm_adjustment"],
        "final_score": adjustment_result["final_score"],
        "adjustment_reason": adjustment_result["adjustment_reason"],
        "keyword_match": formula_result["keyword_match"],
        "section_completeness": formula_result["section_completeness"],
        "formatting": formula_result["formatting"],
        "breakdown": formula_result["breakdown"],
    }

    # ── Persist to SQLite (best-effort, never blocks the response) ──
    if save_to_history:
        try:
            record_id = database.save_analysis(resume_text, job_description, result)
            result["history_id"] = record_id
        except Exception as e:
            result["_persistence_warning"] = str(e)

    return result
