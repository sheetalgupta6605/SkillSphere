
import asyncio
import json

from google import genai

from app.config import settings


def _get_client():
    if not settings.gemini_api_key:
        raise ValueError("Gemini API key is not configured.")

    return genai.Client(api_key=settings.gemini_api_key)


def _prepare_candidates(candidates):
    prepared = []

    for candidate in candidates[:50]:
        prepared.append({
            "candidate_id": str(candidate.get("id", "")),
            "name": candidate.get("full_name", ""),
            "headline": candidate.get("headline", ""),
            "location": candidate.get("location", ""),
            "experience_years": candidate.get("experience_years"),
            "education": candidate.get("education", []),
            "skills": candidate.get("skills", []),
            "profile_completion": candidate.get("profile_completion", 0),
            "resume_available": candidate.get("resume", {}).get("available", False),
        })

    return prepared


def _generate_gemini_response(prompt):
    client = _get_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        },
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return json.loads(response.text)


async def rank_candidates_with_gemini(
    query: str,
    candidates: list[dict],
    job: dict | None = None,
):
    if not candidates:
        return []

    candidate_data = _prepare_candidates(candidates)

    job_data = None

    if job:
        job_data = {
            "title": job.get("title", ""),
            "description": job.get("description", ""),
            "required_skills": job.get("required_skills", []),
            "preferred_skills": job.get("preferred_skills", []),
            "requirements": job.get("requirements", ""),
            "education_requirements": job.get("education_requirements", ""),
            "experience_range": job.get("experience_range", ""),
            "location": job.get("location", ""),
            "job_type": job.get("job_type", ""),
            "work_mode": job.get("work_mode", ""),
        }

    prompt = f"""
You are an AI recruitment assistant for SkillSphere.

Analyze the candidate information and rank candidates according to
their relevance to the recruiter request.

Recruiter request:
{query}

Job details:
{json.dumps(job_data, default=str) if job_data else "No specific job provided."}

Candidates:
{json.dumps(candidate_data, default=str)}

Instructions:
1. Use only the information provided.
2. Do not invent skills, experience, education, or qualifications.
3. Give each candidate a match percentage from 0 to 100.
4. Rank candidates from highest match to lowest match.
5. Explain why each candidate matches the request.
6. Identify matching and missing skills.
7. Include only relevant candidates.
8. Return at most 20 candidates.

Return valid JSON in this exact format:

{{
    "matches": [
        {{
            "candidate_id": "candidate ID",
            "percentage": 85,
            "summary": "Short explanation of the match",
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": ["Docker"],
            "strengths": ["Relevant project experience"],
            "improvements": ["Learn Docker"]
        }}
    ]
}}
"""

    try:
        result = await asyncio.to_thread(
            _generate_gemini_response,
            prompt,
        )

        valid_ids = {
            str(candidate.get("id"))
            for candidate in candidates
        }

        matches = []

        for item in result.get("matches", []):
            candidate_id = str(item.get("candidate_id", ""))

            if candidate_id not in valid_ids:
                continue

            percentage = item.get("percentage", 0)

            if not isinstance(percentage, (int, float)):
                continue

            matches.append({
                "candidate_id": candidate_id,
                "percentage": max(0, min(100, round(percentage))),
                "summary": str(item.get("summary", "")),
                "matched_skills": item.get("matched_skills", []),
                "missing_skills": item.get("missing_skills", []),
                "strengths": item.get("strengths", []),
                "improvements": item.get("improvements", []),
            })

        return matches

    except Exception as exc:
        raise ValueError(
            f"Gemini recruiter matching failed: {exc}"
        ) from exc
