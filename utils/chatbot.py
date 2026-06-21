import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are ResumeIQ, an expert AI resume coach and career advisor. The user has already run a full resume analysis, and that report is included below for context. Your job now is to help them act on it through conversation.

You can help with:
- Improving specific sections (summary, experience, skills, education)
- Rewriting weak bullet points with stronger action verbs and metrics
- Suggesting missing keywords for specific job roles
- ATS optimization tips
- Interview preparation, including deeper follow-up questions
- Tailoring the resume for a specific job description
- Writing a tailored cover letter
- Condensing the resume to one page
- Grammar and language improvements
- General career advice based on their background

Rules:
- Be specific and reference actual content from their resume and the analysis report below
- Give actionable, concrete suggestions, not generic advice
- Keep responses focused and well-formatted (use short paragraphs and bullet points, not giant walls of text)
- If the user pastes a new job description, tailor your advice to that role
- Be encouraging but honest about weaknesses
- Never make up experience or skills the user doesn't have
- When rewriting content (bullets, summary, cover letter), put the final rewritten text clearly so it's easy to copy

Below is the user's resume text and the structured analysis report already generated for them."""


def _format_report_context(report: dict) -> str:
    if not report:
        return "No prior analysis report available."
    try:
        trimmed = {k: v for k, v in report.items() if k not in ("error",)}
        return json.dumps(trimmed, indent=2)[:3000]
    except Exception:
        return "Report unavailable."


def chat_with_resume(user_message: str, resume_text: str, history: list, report: dict = None) -> tuple:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to your .env file (local) or environment variables (Render).")
    client = Groq(api_key=api_key, timeout=30.0)

    report_context = _format_report_context(report)

    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"---RESUME TEXT---\n{resume_text}\n---END RESUME---\n\n"
        f"---ANALYSIS REPORT (JSON)---\n{report_context}\n---END REPORT---"
    )

    messages = [{"role": "system", "content": system}]

    for turn in history:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.5,
        max_tokens=1200,
    )

    reply = response.choices[0].message.content.strip()
    updated_history = history + [{"user": user_message, "assistant": reply}]

    return reply, updated_history
