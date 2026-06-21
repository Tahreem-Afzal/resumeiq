"""
Deterministic ATS scoring engine.

Computes a transparent, explainable base score using a weighted formula:
    ATS Score = (keyword_match% * 0.4) + (section_completeness% * 0.3) + (formatting% * 0.3)

This score is computed BEFORE the LLM call. The LLM is then shown this
formula score and may adjust it by at most +/-5 points, with a stated
reason. This keeps scoring transparent and reproducible rather than
purely a black-box LLM guess.
"""
import re

# Weights for the formula. Must sum to 1.0
WEIGHT_KEYWORDS = 0.4
WEIGHT_SECTIONS = 0.3
WEIGHT_FORMATTING = 0.3

REQUIRED_SECTIONS = {
    "contact": [r"email", r"phone", r"linkedin", r"@", r"\+?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"],
    "summary": [r"\bsummary\b", r"\bobjective\b", r"\bprofile\b"],
    "experience": [r"\bexperience\b", r"\bemployment\b", r"\bwork history\b"],
    "education": [r"\beducation\b", r"\bdegree\b", r"\buniversity\b", r"\bbachelor\b", r"\bb\.?s\.?\b"],
    "skills": [r"\bskills\b", r"\btechnologies\b", r"\btech stack\b"],
    "projects": [r"\bprojects?\b"],
}

FORMATTING_CHECKS = [
    # (regex pattern, points if found, description)
    (r"\n\s*[-•*]\s", 15, "Uses bullet points"),
    (r"\b(19|20)\d{2}\b", 15, "Contains dates/years"),
    (r"@[\w.-]+\.\w+", 15, "Has parseable email"),
    (r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}", 10, "Uses Month YYYY date format"),
]


def _word_set(text: str) -> set:
    """Normalize text into a set of lowercase alphanumeric tokens (1-3 word phrases)."""
    text = text.lower()
    words = re.findall(r"[a-z0-9][a-z0-9+#./-]*", text)
    tokens = set(words)
    # also add bigrams/trigrams for multi-word skills like "machine learning"
    for i in range(len(words) - 1):
        tokens.add(f"{words[i]} {words[i+1]}")
    for i in range(len(words) - 2):
        tokens.add(f"{words[i]} {words[i+1]} {words[i+2]}")
    return tokens


def compute_keyword_match(resume_text: str, job_description: str) -> dict:
    """
    Returns keyword overlap percentage between resume and JD.
    If no JD provided, returns None (caller should fall back to a
    general estimate, e.g. via LLM, since there's nothing to match against).
    """
    if not job_description or not job_description.strip():
        return {"match_percent": None, "matched": [], "missing": []}

    resume_tokens = _word_set(resume_text)
    jd_tokens = _word_set(job_description)

    # Filter JD tokens to "meaningful" ones: skip pure stopword-like short tokens
    stopwords = {
        "the", "and", "for", "with", "a", "an", "to", "of", "in", "on", "is",
        "are", "be", "as", "or", "at", "by", "this", "that", "will", "you",
        "we", "our", "your", "it", "from", "have", "has", "their", "they"
    }
    jd_keywords = {t for t in jd_tokens if t not in stopwords and len(t) > 2}

    if not jd_keywords:
        return {"match_percent": None, "matched": [], "missing": []}

    matched = jd_keywords & resume_tokens
    missing = jd_keywords - resume_tokens

    # Prioritize multi-word phrases and longer tokens in the displayed lists
    # since single short tokens are noisy
    def _rank(tok_set):
        return sorted(tok_set, key=lambda t: (-len(t.split()), -len(t)))

    match_percent = round((len(matched) / len(jd_keywords)) * 100) if jd_keywords else 0

    return {
        "match_percent": min(match_percent, 100),
        "matched": _rank(matched)[:15],
        "missing": _rank(missing)[:15],
    }


def compute_section_completeness(resume_text: str) -> dict:
    """Returns percentage of expected resume sections detected, plus which are missing."""
    text_lower = resume_text.lower()
    detected = {}
    for section, patterns in REQUIRED_SECTIONS.items():
        found = any(re.search(p, text_lower) for p in patterns)
        detected[section] = found

    completeness = round((sum(detected.values()) / len(detected)) * 100)
    missing_sections = [s for s, found in detected.items() if not found]

    return {
        "completeness_percent": completeness,
        "detected": detected,
        "missing_sections": missing_sections,
    }


def compute_formatting_score(resume_text: str) -> dict:
    """Returns a formatting score out of 100 based on simple structural heuristics."""
    score = 0
    found_checks = []
    missing_checks = []

    for pattern, points, description in FORMATTING_CHECKS:
        if re.search(pattern, resume_text, re.IGNORECASE):
            score += points
            found_checks.append(description)
        else:
            missing_checks.append(description)

    # Length heuristic: penalize extremely short or very long resumes
    word_count = len(resume_text.split())
    if 250 <= word_count <= 1100:
        score += 25
        found_checks.append("Resume length is appropriate")
    elif word_count < 250:
        missing_checks.append("Resume seems too short for ATS to extract enough signal")
    else:
        missing_checks.append("Resume may be too long (consider condensing to 1-2 pages)")

    # Penalize excessive special characters that can break ATS parsers (tables, columns, icons)
    special_char_ratio = len(re.findall(r"[^\w\s.,;:()\-/&@%+]", resume_text)) / max(len(resume_text), 1)
    if special_char_ratio < 0.02:
        score += 10
        found_checks.append("Minimal special characters/symbols that could confuse ATS parsers")
    else:
        missing_checks.append("Contains symbols/characters that some ATS parsers may misread")

    return {
        "formatting_percent": min(score, 100),
        "found_checks": found_checks,
        "missing_checks": missing_checks,
    }


def compute_ats_formula_score(resume_text: str, job_description: str = "") -> dict:
    """
    Main entry point. Computes the full weighted ATS score breakdown.

    Returns a dict with:
        - formula_score: int (0-100), the final weighted score
        - keyword_match: dict
        - section_completeness: dict
        - formatting: dict
        - breakdown: dict showing each component's contribution
    """
    keyword_result = compute_keyword_match(resume_text, job_description)
    section_result = compute_section_completeness(resume_text)
    formatting_result = compute_formatting_score(resume_text)

    # If no JD, keyword component is excluded from the formula and weight
    # is redistributed proportionally between sections + formatting.
    if keyword_result["match_percent"] is None:
        section_weight = WEIGHT_SECTIONS / (WEIGHT_SECTIONS + WEIGHT_FORMATTING)
        formatting_weight = WEIGHT_FORMATTING / (WEIGHT_SECTIONS + WEIGHT_FORMATTING)
        formula_score = (
            section_result["completeness_percent"] * section_weight
            + formatting_result["formatting_percent"] * formatting_weight
        )
        breakdown = {
            "keyword_contribution": None,
            "section_contribution": round(section_result["completeness_percent"] * section_weight, 1),
            "formatting_contribution": round(formatting_result["formatting_percent"] * formatting_weight, 1),
            "weights_used": {"sections": round(section_weight, 2), "formatting": round(formatting_weight, 2)},
        }
    else:
        formula_score = (
            keyword_result["match_percent"] * WEIGHT_KEYWORDS
            + section_result["completeness_percent"] * WEIGHT_SECTIONS
            + formatting_result["formatting_percent"] * WEIGHT_FORMATTING
        )
        breakdown = {
            "keyword_contribution": round(keyword_result["match_percent"] * WEIGHT_KEYWORDS, 1),
            "section_contribution": round(section_result["completeness_percent"] * WEIGHT_SECTIONS, 1),
            "formatting_contribution": round(formatting_result["formatting_percent"] * WEIGHT_FORMATTING, 1),
            "weights_used": {
                "keywords": WEIGHT_KEYWORDS,
                "sections": WEIGHT_SECTIONS,
                "formatting": WEIGHT_FORMATTING,
            },
        }

    return {
        "formula_score": round(formula_score),
        "keyword_match": keyword_result,
        "section_completeness": section_result,
        "formatting": formatting_result,
        "breakdown": breakdown,
    }


def apply_llm_adjustment(formula_score: int, llm_adjustment: int, llm_reason: str) -> dict:
    """
    Applies a bounded LLM adjustment (+/-5 max) to the formula score.
    Used to keep the LLM's influence transparent and capped.
    """
    clamped_adjustment = max(-5, min(5, llm_adjustment))
    final_score = max(0, min(100, formula_score + clamped_adjustment))

    return {
        "formula_score": formula_score,
        "llm_adjustment": clamped_adjustment,
        "final_score": final_score,
        "adjustment_reason": llm_reason,
    }
