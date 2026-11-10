import pytest

from app.services.resume_matching import analyze_resume_match


def test_weighted_match_uses_resume_text_and_excludes_duplicate_skills():
    resume = {"extracted_data": {"raw_text": "4 years as a Python and React developer. BSc Computer Science.", "skills": ["PYTHON", "React.js", "AWS"], "education": ["BSc Computer Science"]}}
    job = {"required_skills": ["Python", "React", "JavaScript"], "preferred_skills": ["AWS", "React"], "experience_range": "3+ years", "education_requirements": ["Bachelor's degree"]}

    result = analyze_resume_match(resume, job)

    assert result["matched_skills"] == ["Python", "React"]
    assert result["missing_skills"] == ["JavaScript"]
    assert result["preferred_skill_results"] == {"matched": ["AWS"], "missing": [], "available": True}
    assert result["experience_comparison"]["status"] == "meets"
    assert result["education_comparison"]["status"] == "meets"
    assert result["available_weight"] == 100
    assert result["percentage"] == 80


def test_unlisted_categories_are_excluded_and_no_criteria_is_not_a_full_score():
    resume = {"extracted_data": {"raw_text": "I build software products.", "skills": []}}

    result = analyze_resume_match(resume, {"required_skills": ["Python"]})
    assert result["percentage"] == 0
    assert result["available_weight"] == 60
    assert "education" in result["excluded_categories"]

    empty = analyze_resume_match(resume, {})
    assert empty["percentage"] is None
    assert empty["available_weight"] == 0


def test_missing_extracted_resume_text_is_rejected():
    with pytest.raises(ValueError, match="no extracted text"):
        analyze_resume_match({"extracted_data": {"raw_text": " "}}, {"required_skills": ["Python"]})


def test_education_field_mismatch_is_not_counted_as_a_match():
    result = analyze_resume_match(
        {"extracted_data": {"raw_text": "Bachelor of Arts in History", "education": ["Bachelor of Arts in History"]}},
        {"education_requirements": ["Bachelor's degree in Computer Science"]},
    )
    assert result["education_comparison"]["status"] == "field_mismatch"
    assert result["percentage"] == 0
