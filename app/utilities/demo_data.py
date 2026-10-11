from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.database import ensure_db_and_tables, get_cli_session
from app.models.student_awards import VolunteerHour
from app.repositories.student_awards import StudentAwardsRepository
from app.repositories.user import UserRepository
from app.schemas.user import AdminCreate, RegularUserCreate
from app.utilities.security import encrypt_password


@dataclass(frozen=True)
class SeedSummary:
    users_created: int
    users_skipped: int
    submissions_created: int
    redemptions_created: int


DEMO_USERS = (
    ("bob", "bob@example.com", "bobpass", "Bob", "Student", "regular_user"),
    ("admin", "admin@example.com", "adminpass", "Ari", "Admin", "admin"),
    ("maya", "maya@example.com", "studentpass", "Maya", "Chen", "regular_user"),
    ("jordan", "jordan@example.com", "studentpass", "Jordan", "Reed", "regular_user"),
    ("alex", "alex@example.com", "studentpass", "Alex", "Morgan", "regular_user"),
    ("taylor", "taylor@example.com", "studentpass", "Taylor", "Singh", "regular_user"),
)

DEMO_SUBMISSIONS = (
    (
        "bob", 8, "Campus Garden Cleanup", 8, "Kingston Community Garden",
        "Helped prepare planting beds.", "Approved", "",
    ),
    (
        "bob", 2, "Library Book Drive", 2, "Campus Library",
        "Sorted donated books.", "Pending", "",
    ),
    (
        "bob", 1, "Food Pantry Sorting", 5, "Student Food Pantry",
        "Assisted with a weekly food delivery.", "Rejected",
        "Please include the volunteer coordinator's confirmation.",
    ),
    (
        "maya", 8, "Peer Tutoring", 9, "Student Learning Centre",
        "Tutored first-year students in biology.", "Approved", "",
    ),
    (
        "maya", 6, "Community Food Bank", 4, "Kingston Food Bank",
        "Packed grocery hampers.", "Approved", "",
    ),
    (
        "jordan", 18, "Orientation Week Crew", 11, "Student Union",
        "Welcomed new students during orientation.", "Approved", "",
    ),
    (
        "jordan", 20, "Neighbourhood Cleanup", 6, "Downtown Neighbours",
        "Joined a community park cleanup.", "Approved", "",
    ),
    (
        "alex", 30, "Community Health Fair", 14, "Campus Wellness Centre",
        "Helped coordinate the annual health fair.", "Approved", "",
    ),
    (
        "alex", 24, "After-School Reading Club", 7, "Riverside Youth Centre",
        "Read with elementary students.", "Approved", "",
    ),
    (
        "taylor", 3, "Campus Welcome Desk", 1, "Student Union",
        "Covered a welcome desk shift.", "Pending", "",
    ),
)


def seed_demo_data() -> SeedSummary:
    """Create repeatable accounts and sample records for the Student Awards UI."""
    ensure_db_and_tables()
    users_created = 0
    users_skipped = 0
    submissions_created = 0
    redemptions_created = 0

    with get_cli_session() as session:
        users = UserRepository(session)
        awards = StudentAwardsRepository(session)
        awards.ensure_default_award_catalog()
        student_ids: dict[str, int] = {}

        for username, email, password, first_name, last_name, role in DEMO_USERS:
            user = users.get_by_username(username)
            if user is None:
                payload_type = AdminCreate if role == "admin" else RegularUserCreate
                user = users.create(
                    payload_type(
                        username=username,
                        email=email,
                        password=encrypt_password(password),
                        role=role,
                    )
                )
                if user is None:
                    raise RuntimeError(f"Could not create demo user {username}.")
                users_created += 1
            else:
                users_skipped += 1

            if user.role != role:
                raise RuntimeError(
                    f"Demo username {username} has role {user.role!r}; expected {role!r}."
                )
            if user.id is None:
                raise RuntimeError(f"Demo user {username} has not been saved.")

            if role == "admin":
                admin = awards.get_admin_by_user_id(user.id)
                if admin is None:
                    admin = awards.create_admin_profile(user_id=user.id)
                if admin.id is None:
                    raise RuntimeError("The demo admin profile has not been saved.")
            else:
                student = awards.get_student_by_user_id(user.id)
                if student is None:
                    student = awards.create_student(
                        user_id=user.id,
                        first_name=first_name,
                        last_name=last_name,
                    )
                if student.id is None:
                    raise RuntimeError(f"Demo student {username} has not been saved.")
                student_ids[username] = student.id

        demo_admin = users.get_by_username("admin")
        if demo_admin is None or demo_admin.id is None:
            raise RuntimeError("The demo admin account has not been saved.")
        admin_profile = awards.get_admin_by_user_id(demo_admin.id)
        if admin_profile is None or admin_profile.id is None:
            raise RuntimeError("The demo admin profile has not been saved.")

        today = date.today()
        for (
            username,
            hours_logged,
            activity,
            days_ago,
            organisation,
            student_notes,
            status,
            admin_notes,
        ) in DEMO_SUBMISSIONS:
            student_id = student_ids[username]
            existing = awards.get_volunteer_hours_for_student(student_id)
            existing_keys = {
                (submission.activity, submission.organisation)
                for submission in existing
            }
            key = (activity, organisation)
            if key in existing_keys:
                continue

            submitted_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                days=days_ago
            )
            reviewed = status != "Pending"
            awards.create_volunteer_hour(
                VolunteerHour(
                    student_id=student_id,
                    admin_id=admin_profile.id if reviewed else None,
                    hours_logged=hours_logged,
                    activity=activity,
                    activity_date=today - timedelta(days=days_ago + 1),
                    organisation=organisation,
                    student_notes=student_notes,
                    submitted_at=submitted_at,
                    status=status,
                    approved_at=(
                        submitted_at + timedelta(hours=3)
                        if status == "Approved"
                        else None
                    ),
                    admin_notes=admin_notes or None,
                )
            )
            submissions_created += 1

        jordan_id = student_ids["jordan"]
        bronze_badge = next(
            (reward for reward in awards.get_rewards() if reward.name == "Bronze Badge"),
            None,
        )
        if bronze_badge is None or bronze_badge.id is None:
            raise RuntimeError("The default Bronze Badge reward is missing.")
        jordan_claims = awards.get_claimed_rewards(jordan_id)
        if not any(reward.id == bronze_badge.id for _, reward in jordan_claims):
            awards.create_reward_redemption(
                student_id=jordan_id,
                reward_id=bronze_badge.id,
                redeemed_at=today - timedelta(days=3),
            )
            redemptions_created += 1

    return SeedSummary(
        users_created=users_created,
        users_skipped=users_skipped,
        submissions_created=submissions_created,
        redemptions_created=redemptions_created,
    )
