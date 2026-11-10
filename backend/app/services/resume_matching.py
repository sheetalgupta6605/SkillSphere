import re

from app.services.resume import normalize_skill


SKILL_VOCABULARY = (
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go", "Rust", "PHP", "Ruby", "Kotlin", "Swift",
    "React", "Angular", "Vue", "Next.js", "Node.js", "Express", "FastAPI", "Django", "Flask", "Spring", ".NET",
    "HTML", "CSS", "Tailwind", "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "AWS", "Azure", "GCP", "Docker", "Kubernetes",
    "Git", "Linux", "REST API", "GraphQL", "Machine Learning", "Data Analysis", "Pandas", "NumPy", "TensorFlow", "PyTorch",
    "Figma", "UI/UX", "Excel", "Power BI", "Tableau", "Project Management", "Communication",
)
EDUCATION_TERMS = ("degree", "bachelor", "b.sc", "bsc", "undergraduate", "master", "m.sc", "msc", "ph.d", "phd", "doctorate", "diploma", "associate", "high school", "graduate", "graduation")


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _contains(text: str, term: str) -> bool:
    if not term.strip():
        return False
    return bool(re.search(r"(?<![\w.+#-])" + re.escape(term.strip()) + r"(?![\w.+#-])", text, re.IGNORECASE))


def _dedupe_skills(skills: list[str]) -> dict[str, str]:
    result = {}
    for skill in skills:
        canonical = normalize_skill(skill)
        if canonical:
            result.setdefault(canonical, skill.strip())
    return result


def _skills_in_text(text: str, candidates: list[str]) -> dict[str, str]:
    found = {}
    for skill in candidates:
        canonical = normalize_skill(skill)
        if canonical and (_contains(text, skill) or _contains(text, canonical)):
            found.setdefault(canonical, skill.strip())
    return found


def _experience_requirement(job: dict) -> str:
    if job.get("experience_range"):
        return str(job["experience_range"]).strip()
    for line in _as_list(job.get("requirements")):
        if re.search(r"\d+(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)", line, re.IGNORECASE):
            return line
    return ""


def _experience_years(text: str) -> float | None:
    values = [float(value) for value in re.findall(r"(?<!\d)(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", text, re.IGNORECASE)]
    return max(values) if values else None


def _education_requirements(job: dict) -> list[str]:
    explicit = _as_list(job.get("education_requirements")) or _as_list(job.get("education_required"))
    for line in _as_list(job.get("requirements")):
        if any(term in line.lower() for term in EDUCATION_TERMS):
            explicit.append(line)
    return list(dict.fromkeys(explicit))


def _education_level(text: str) -> int | None:
    normalized = text.lower()
    if re.search(r"\b(ph\.?d|doctorate)\b", normalized):
        return 4
    if re.search(r"\b(master'?s?|m\.?sc|mba|postgraduate)\b", normalized):
        return 3
    if re.search(r"\b(bachelor'?s?|b\.?sc|undergraduate|b\.?tech|b\.?e\.?|bca)\b", normalized):
        return 2
    if re.search(r"\b(diploma|associate)\b", normalized):
        return 1
    return None


def _education_field_terms(requirement: str) -> list[str]:
    field = re.sub(r"\b(ph\.?d|doctorate|master'?s?|bachelor'?s?|undergraduate|postgraduate|m\.?sc|b\.?sc|mba|b\.?tech|b\.?e\.?|bca|associate|diploma|high school|degree|graduate|graduation|in|of|the|a|an|required|preferred)\b", " ", requirement.lower())
    return re.findall(r"[a-z][a-z+#.]{2,}", field)


def analyze_resume_match(resume: dict, job: dict) -> dict:
    extracted = resume.get("extracted_data") or {}
    raw_text = str(extracted.get("raw_text") or "")[:30000]
    if not raw_text.strip():
        raise ValueError("This resume has no extracted text. Reprocess it or upload a readable PDF first.")

    parsed_skills = _as_list(extracted.get("skills"))
    candidate_skill_map = _dedupe_skills(parsed_skills)
    requirements_lines = _as_list(job.get("requirements"))
    required_raw = _as_list(job.get("required_skills"))
    preferred_raw = _as_list(job.get("preferred_skills"))
    recognized_required = []
    recognized_preferred = []
    for line in requirements_lines:
        destination = recognized_preferred if "preferred" in line.lower() or "nice to have" in line.lower() else recognized_required
        destination.extend(skill for skill in SKILL_VOCABULARY if _contains(line, skill))
    required_map = _dedupe_skills(required_raw + recognized_required)
    preferred_map = {key: label for key, label in _dedupe_skills(preferred_raw + recognized_preferred).items() if key not in required_map}

    all_target_skills = list(required_map) + [skill for skill in preferred_map if skill not in required_map]
    text_skill_map = _skills_in_text(raw_text, [*all_target_skills, *SKILL_VOCABULARY])
    resume_skill_keys = set(candidate_skill_map) | set(text_skill_map)
    required_matched_keys = set(required_map) & resume_skill_keys
    required_missing_keys = set(required_map) - required_matched_keys
    preferred_matched_keys = set(preferred_map) & resume_skill_keys
    preferred_missing_keys = set(preferred_map) - preferred_matched_keys
    required_matched = [required_map[key] for key in required_map if key in required_matched_keys]
    required_missing = [required_map[key] for key in required_map if key in required_missing_keys]
    preferred_matched = [preferred_map[key] for key in preferred_map if key in preferred_matched_keys]
    preferred_missing = [preferred_map[key] for key in preferred_map if key in preferred_missing_keys]

    weights = {"required_skills": 60, "preferred_skills": 20, "experience": 10, "education": 10}
    earned_weight = 0.0
    available_weight = 0
    components = []

    def add_component(key: str, score: float, details: dict):
        nonlocal earned_weight, available_weight
        weight = weights[key]
        available_weight += weight
        earned_weight += weight * score
        components.append({"key": key, "weight": weight, "score": round(score * 100), **details})

    if required_map:
        add_component("required_skills", len(required_matched_keys) / len(required_map), {"available": True, "matched": required_matched, "missing": required_missing})
    if preferred_map:
        add_component("preferred_skills", len(preferred_matched_keys) / len(preferred_map), {"available": True, "matched": preferred_matched, "missing": preferred_missing})

    experience_requirement = _experience_requirement(job)
    experience_result = {"available": bool(experience_requirement), "requirement": experience_requirement or None, "candidate_years_found": None, "status": "not_specified", "score": None}
    if experience_requirement:
        required_years_match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", experience_requirement, re.IGNORECASE)
        candidate_years = _experience_years(raw_text)
        experience_result["candidate_years_found"] = candidate_years
        experience_result["status"] = "insufficient_evidence"
        experience_result["score"] = 0
        if required_years_match and candidate_years is not None:
            minimum_years = float(required_years_match.group(1))
            ratio = 1.0 if minimum_years <= 0 else min(1.0, candidate_years / minimum_years)
            experience_result["score"] = round(ratio * 100)
            experience_result["status"] = "meets" if candidate_years >= minimum_years else "below"
        elif _contains(raw_text, experience_requirement):
            experience_result["score"] = 100
            experience_result["status"] = "mentioned"
        add_component("experience", experience_result["score"] / 100, {**experience_result, "available": True})

    education_requirements = _education_requirements(job)
    education_text = " ".join(_as_list(extracted.get("education")))
    education_text = education_text or raw_text
    education_result = {"available": bool(education_requirements), "requirements": education_requirements, "evidence": _as_list(extracted.get("education")), "status": "not_specified", "score": None}
    if education_requirements:
        required_levels = [_education_level(requirement) for requirement in education_requirements]
        candidate_level = _education_level(education_text)
        exact_matches = [requirement for requirement in education_requirements if _contains(education_text, requirement)]
        level_requirements = [level for level in required_levels if level is not None]
        if level_requirements and candidate_level is not None:
            has_required_field = all(all(_contains(education_text, term) for term in _education_field_terms(requirement)) for requirement in education_requirements)
            education_score = 100 if candidate_level >= max(level_requirements) and has_required_field else 0
            education_status = "meets" if education_score else "field_mismatch" if candidate_level >= max(level_requirements) and not has_required_field else "below"
        else:
            education_score = 100 if exact_matches else 0
            education_status = "matches" if exact_matches else "not_found"
        education_result.update({"status": education_status, "score": education_score})
        add_component("education", education_score / 100, {**education_result, "available": True})

    percentage = round(earned_weight / available_weight * 100) if available_weight else None
    suggestions = [f"If you have experience with {skill}, describe a relevant project or result in your resume." for skill in required_missing[:5]]
    if experience_requirement and experience_result["status"] in {"below", "insufficient_evidence"}:
        suggestions.append("Add dates and specific responsibilities for relevant experience, if applicable.")
    if education_requirements and education_result["status"] in {"below", "not_found"}:
        suggestions.append("List relevant education or certifications you have earned; do not add qualifications you do not hold.")
    if not suggestions:
        suggestions.append("Keep your resume accurate and specific; this score is a requirement overlap, not a hiring prediction.")
    skipped = [key.replace("_", " ") for key in weights if key not in {component["key"] for component in components}]
    explanation = f"Weighted score: {available_weight}% of the rubric was available for this job; unlisted requirement categories were excluded. This is not a guarantee of selection."

    return {
        "percentage": percentage,
        "available_weight": available_weight,
        "components": components,
        "excluded_categories": skipped,
        "matched_skills": required_matched,
        "missing_skills": required_missing,
        "preferred_skill_results": {"matched": preferred_matched, "missing": preferred_missing, "available": bool(preferred_map)},
        "experience_comparison": experience_result,
        "education_comparison": education_result,
        "improvement_suggestions": suggestions,
        "explanation": explanation,
        "disclaimer": "This score compares extracted resume evidence with listed job requirements. It does not predict hiring outcomes.",
    }
