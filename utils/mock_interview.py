"""
Agent 3: Mock Interview Agent.

Split into two roles, matching the multi-agent framing used elsewhere in
this project (analogous to the specialist-panel idea in the Diagnostic
Disagreement Panel project):

  - Interviewer agent: asks the next question, conditioned on the resume,
    JD, and everything asked/answered so far (won't repeat topics).
  - Evaluator agent: scores the candidate's last answer independently,
    using a fixed rubric (STAR structure, specificity, relevance).

Keeping these separate (rather than one agent doing both) means the
evaluator's rubric-based score is a clean, independently-reportable
metric for the paper (e.g. inter-question score variance, rubric
dimension breakdown) rather than being entangled with question
generation.

This module is stateless — the Flask layer is responsible for
persisting `transcript` across requests (e.g. in session, like
utils/chatbot.py does with chat_history).
"""
from utils.agent_client import call_json, call_text

RUBRIC_DIMENSIONS = ["structure_star", "specificity", "relevance_to_role", "confidence_clarity"]


INTERVIEWER_SYSTEM = """You are an experienced technical/behavioral interviewer conducting a mock interview. Ask ONE question at a time. Base questions on the candidate's resume and the target job description. Mix behavioral and role-specific technical questions. Never repeat a topic already covered in the transcript. Keep questions concise (1-3 sentences)."""


def generate_question(resume_text: str, job_description: str, transcript: list) -> dict:
    covered = "\n".join(f"- Q: {t['question']}" for t in transcript) or "(none yet — this is the first question)"

    prompt = f"""RESUME:
\"\"\"
{resume_text[:3000]}
\"\"\"

JOB DESCRIPTION:
\"\"\"
{job_description[:2000] if job_description else "(none provided — ask general role-appropriate questions based on the resume)"}
\"\"\"

QUESTIONS ALREADY ASKED:
{covered}

Ask the next interview question. Return ONLY valid JSON, no markdown:
{{
  "question": "<the interview question>",
  "focus_area": "<short label, e.g. 'Leadership', 'System Design', 'Past Project Deep-dive'>",
  "question_type": "<'behavioral' or 'technical'>"
}}"""
    try:
        return call_json(prompt, temperature=0.6, max_tokens=400, system=INTERVIEWER_SYSTEM)
    except Exception as e:
        return {
            "question": "Tell me about a challenging project you worked on and how you approached it.",
            "focus_area": "General",
            "question_type": "behavioral",
            "_fallback_reason": str(e),
        }


EVALUATOR_PROMPT_TEMPLATE = """You are a strict interview evaluator. Score the CANDIDATE ANSWER to the QUESTION below on a fixed rubric. Be honest, not encouraging-by-default.

QUESTION: {question}
CANDIDATE ANSWER: \"\"\"{answer}\"\"\"

RESUME CONTEXT (for checking specificity/consistency):
\"\"\"
{resume_text}
\"\"\"

Score each rubric dimension 1-10:
- structure_star: Did they use a clear Situation/Task/Action/Result structure (for behavioral) or clear logical structure (for technical)?
- specificity: Concrete details, numbers, technologies named vs. vague generalities?
- relevance_to_role: Does the answer connect to the target role/JD?
- confidence_clarity: Is the answer clear and confidently delivered (based on wording, not tone of voice)?

Return ONLY valid JSON, no markdown:
{{
  "scores": {{"structure_star": <1-10>, "specificity": <1-10>, "relevance_to_role": <1-10>, "confidence_clarity": <1-10>}},
  "overall_score": <1-10, your holistic judgment, need not be the average>,
  "strengths": [<1-3 specific strengths in this answer>],
  "improvements": [<1-3 specific, actionable improvements>],
  "ideal_answer_sketch": "<2-3 sentence sketch of what a stronger answer would include>"
}}"""


def evaluate_answer(question: str, answer: str, resume_text: str) -> dict:
    prompt = EVALUATOR_PROMPT_TEMPLATE.format(
        question=question,
        answer=answer[:2000],
        resume_text=resume_text[:2500],
    )
    try:
        return call_json(prompt, temperature=0.1, max_tokens=800)
    except Exception as e:
        return {
            "scores": {dim: None for dim in RUBRIC_DIMENSIONS},
            "overall_score": None,
            "strengths": [],
            "improvements": [],
            "ideal_answer_sketch": "",
            "_error": str(e),
        }


def run_interview_turn(resume_text: str, job_description: str, transcript: list, user_answer: str = None) -> dict:
    """
    Orchestrates one turn:
      - If `user_answer` is given, evaluates it against the LAST question in
        the transcript (appends the evaluation to that turn).
      - Always generates and appends the next question.

    `transcript` is a list of turns: [{"question", "focus_area", "question_type", "answer"?, "evaluation"?}, ...]
    Returns the updated transcript plus the newly generated question for convenience.
    """
    transcript = list(transcript)  # don't mutate caller's list in place unexpectedly

    if user_answer is not None and transcript:
        last_turn = transcript[-1]
        last_turn["answer"] = user_answer
        last_turn["evaluation"] = evaluate_answer(last_turn["question"], user_answer, resume_text)

    next_q = generate_question(resume_text, job_description, transcript)
    transcript.append({
        "question": next_q.get("question"),
        "focus_area": next_q.get("focus_area"),
        "question_type": next_q.get("question_type"),
    })

    return {"transcript": transcript, "current_question": next_q}


def summarize_interview(transcript: list) -> dict:
    """Aggregates rubric scores across all answered questions into a final report."""
    answered = [t for t in transcript if t.get("evaluation") and t["evaluation"].get("overall_score") is not None]

    if not answered:
        return {"questions_answered": 0, "average_overall_score": None, "dimension_averages": {}, "summary": "No answers evaluated yet."}

    avg_overall = round(sum(t["evaluation"]["overall_score"] for t in answered) / len(answered), 2)
    dim_avgs = {}
    for dim in RUBRIC_DIMENSIONS:
        vals = [t["evaluation"]["scores"].get(dim) for t in answered if t["evaluation"]["scores"].get(dim) is not None]
        dim_avgs[dim] = round(sum(vals) / len(vals), 2) if vals else None

    weakest_dim = min((d for d in dim_avgs if dim_avgs[d] is not None), key=lambda d: dim_avgs[d], default=None)

    summary_prompt = f"""Given these mock interview rubric averages: {dim_avgs}, and overall average {avg_overall}/10 across {len(answered)} questions, write a 2-3 sentence coaching summary highlighting the strongest and weakest dimension. Be direct and specific, not generic."""
    try:
        summary_text = call_text(summary_prompt, temperature=0.4, max_tokens=200)
    except Exception:
        summary_text = f"Average score {avg_overall}/10 across {len(answered)} questions. Weakest area: {weakest_dim}."

    return {
        "questions_answered": len(answered),
        "average_overall_score": avg_overall,
        "dimension_averages": dim_avgs,
        "weakest_dimension": weakest_dim,
        "summary": summary_text,
    }