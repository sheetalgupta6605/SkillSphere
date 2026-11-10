from app.database import get_database


# These are the collections required by the project database plan. The older
# candidate_profiles and recruiter_profiles collections are kept for the
# existing API routes and are indexed below as compatibility collections.
REQUIRED_COLLECTIONS = (
    "users",
    "candidates",
    "recruiters",
    "companies",
    "resumes",
    "skills",
    "jobs",
    "applications",
    "resume_analyses",
    "notifications",
    "saved_jobs",
    "job_views",
    "saved_candidates",
    "saved_searches",
    "user_preferences",
)


async def create_indexes() -> None:
    db = get_database()

    # Create empty collections explicitly so the complete database structure
    # is visible in Atlas before each feature has inserted its first record.
    existing_collections = set(await db.list_collection_names())
    for collection_name in REQUIRED_COLLECTIONS:
        if collection_name not in existing_collections:
            await db.create_collection(collection_name)

    # Authentication and one-profile-per-user constraints.
    await db.users.create_index("email", unique=True)
    await db.candidates.create_index("user_id", unique=True)
    await db.candidates.create_index([("recruiter_discoverable", 1), ("updated_at", -1)])
    await db.recruiters.create_index("user_id", unique=True)
    await db.candidate_profiles.create_index("user_id", unique=True)
    await db.candidate_profiles.create_index([("recruiter_discoverable", 1), ("updated_at", -1)])
    await db.recruiter_profiles.create_index("user_id", unique=True)

    # Company ownership and standardized skills.
    await db.companies.create_index("recruiter_id", unique=True)
    await db.skills.create_index("normalized_name", unique=True)

    # Job search and ordering.
    await db.jobs.create_index([("status", 1), ("created_at", -1)])
    await db.jobs.create_index([("status", 1), ("location", 1), ("created_at", -1)])
    await db.jobs.create_index([("status", 1), ("job_type", 1), ("created_at", -1)])
    await db.jobs.create_index([("status", 1), ("recruiter_id", 1), ("created_at", -1)])
    await db.jobs.create_index([("status", 1), ("work_mode", 1), ("created_at", -1)])
    await db.jobs.create_index("required_skills")
    await db.jobs.create_index(
        [("title", "text"), ("description", "text"), ("required_skills", "text")]
    )

    # Application uniqueness and candidate/recruiter query patterns.
    await db.applications.create_index(
        [("candidate_id", 1), ("job_id", 1)], unique=True
    )
    await db.applications.create_index([("job_id", 1), ("status", 1)])
    await db.applications.create_index([("candidate_id", 1), ("created_at", -1)])
    await db.applications.create_index("status")

    # Resume ownership and matching history.
    await db.resumes.create_index([("candidate_id", 1), ("created_at", -1)])
    await db.resume_analyses.create_index([("candidate_id", 1), ("created_at", -1)])
    await db.resume_analyses.create_index([("job_id", 1), ("created_at", -1)])

    # Private notifications and saved/recent jobs.
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("is_read", 1), ("created_at", -1)])
    await db.user_preferences.create_index("user_id", unique=True)
    await db.saved_jobs.create_index(
        [("candidate_id", 1), ("job_id", 1)], unique=True
    )
    await db.job_views.create_index(
        [("candidate_id", 1), ("job_id", 1)], unique=True
    )
    await db.job_views.create_index([("candidate_id", 1), ("viewed_at", -1)])
    await db.saved_candidates.create_index([("recruiter_id", 1), ("candidate_id", 1)], unique=True)
    await db.saved_candidates.create_index([("recruiter_id", 1), ("created_at", -1)])
    await db.saved_searches.create_index([("recruiter_id", 1), ("name", 1)], unique=True)
    await db.saved_searches.create_index([("recruiter_id", 1), ("updated_at", -1)])

    # Existing messaging features.
    await db.messages.create_index([("recipient_id", 1), ("is_read", 1), ("created_at", -1)])
    await db.messages.create_index([("sender_id", 1), ("recipient_id", 1), ("created_at", 1)])

    print(f"MongoDB collections and indexes initialized ({len(REQUIRED_COLLECTIONS)} required collections).")
