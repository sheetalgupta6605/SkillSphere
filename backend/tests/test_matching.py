from app.services.resume import normalize_skill


def calculate_match(required: list[str], candidate: list[str]) -> int | None:
    required_set = {normalize_skill(skill) for skill in required if skill.strip()}
    candidate_set = {normalize_skill(skill) for skill in candidate if skill.strip()}
    return round(len(required_set & candidate_set) / len(required_set) * 100) if required_set else None


def test_matching_formula():
    assert calculate_match(["Python", "React", "Docker", "JS"], ["python", "react.js", "javascript"]) == 75


def test_empty_requirements_are_safe():
    assert calculate_match([], ["Python"]) is None
