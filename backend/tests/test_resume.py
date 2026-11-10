from app.services.resume import normalize_skill, parse_resume_text


def test_skill_aliases_are_normalized():
    assert normalize_skill("JS") == "javascript"
    assert normalize_skill("React") == "react.js"


def test_resume_parser_extracts_real_values_without_inventing_data():
    result = parse_resume_text("Asha Rao\nasha@example.com\nPython and React", ["Python", "React", "Docker"])
    assert result["name"] == "Asha Rao"
    assert result["email"] == "asha@example.com"
    assert result["skills"] == ["python", "react.js"]
    assert "Docker" not in result["skills"]
