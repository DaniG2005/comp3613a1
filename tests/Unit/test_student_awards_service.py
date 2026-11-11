from datetime import date
from unittest.mock import MagicMock

import pytest

from app.models.student_awards import (
    Admin,
    Reward,
    Student,
    VolunteerHour,
)
from app.repositories.student_awards import StudentAwardsRepository
from app.services.student_awards import (
    StudentAwardsService,
    StudentDashboardSummary,
)


@pytest.fixture
def repo():
    return MagicMock(spec=StudentAwardsRepository)


@pytest.fixture
def serv(repo):
    return StudentAwardsService(repo)


@pytest.fixture
def stu():
    return Student(
        id=10,
        user_id=1,
        first_name="Bob",
        last_name="Student",
    )

def test_log_volunteer_hours_creates_pending_submission(
    serv,
    repo,
    stu,
):
    repo.get_student_by_user_id.return_value = stu
    repo.create_volunteer_hour.side_effect = lambda submission: submission

    result = serv.log_volunteer_hours(
        user_id=1,
        hours_logged=5,
        activity="Food Drive",
        activity_date=date(2026, 11, 1),
        organisation="UWI",
        student_notes="Helped distribute food.",
    )

    assert result.student_id == 10
    assert result.hours_logged == 5
    assert result.activity == "Food Drive"
    assert result.organisation == "UWI"
    assert result.status == "Pending"

    repo.get_student_by_user_id.assert_called_once_with(1)
    repo.create_volunteer_hour.assert_called_once()


def test_log_volunteer_hours_rejects_zero_hours(
    serv,
    repo,
):
    with pytest.raises(
        ValueError,
        match="Hours logged must be a positive integer",
    ):
        serv.log_volunteer_hours(
            user_id=1,
            hours_logged=0,
            activity="Food Drive",
            activity_date=date(2026, 11, 1),
            organisation="UWI",
            student_notes="",
        )

    repo.create_volunteer_hour.assert_not_called()


def test_log_volunteer_hours_rejects_missing_student_profile(
    serv,
    repo,
):
    repo.get_student_by_user_id.return_value = None

    with pytest.raises(
        ValueError,
        match="student profile is not set up",
    ):
        serv.log_volunteer_hours(
            user_id=999,
            hours_logged=5,
            activity="Food Drive",
            activity_date=date(2026, 11, 1),
            organisation="UWI",
            student_notes="",
        )

    repo.create_volunteer_hour.assert_not_called()

def test_admin_can_approve_pending_submission(
    serv,
    repo,
    stu,
):
    admin = Admin(
        id=2,
        user_id=50,
    )

    submission = VolunteerHour(
        id=20,
        student_id=stu.id,
        hours_logged=5,
        activity="Food Drive",
        activity_date=date(2026, 11, 1),
        organisation="UWI",
        status="Pending",
    )

    approved_submission = VolunteerHour(
        id=20,
        student_id=stu.id,
        admin_id=admin.id,
        hours_logged=5,
        activity="Food Drive",
        activity_date=date(2026, 11, 1),
        organisation="UWI",
        status="Approved",
    )

    repo.get_admin_by_user_id.return_value = admin
    repo.get_submission_for_review.return_value = (
        submission,
        stu,
        "bob",
    )
    repo.save_submission_review.return_value = approved_submission

    result = serv.review_hour_submission(
        submission_id=20,
        admin_user_id=50,
        decision="Approved",
        admin_notes="Verified.",
    )

    assert result.status == "Approved"

    repo.save_submission_review.assert_called_once_with(
        submission=submission,
        admin_id=2,
        decision="Approved",
        admin_notes="Verified.",
    )


def test_rejected_submission_requires_admin_notes(
    serv,
    repo,
):
    with pytest.raises(
        ValueError,
        match="Admin notes are required",
    ):
        serv.review_hour_submission(
            submission_id=20,
            admin_user_id=50,
            decision="Rejected",
            admin_notes="",
        )

    repo.save_submission_review.assert_not_called()


def test_submission_cannot_be_reviewed_twice(
    serv,
    repo,
    stu,
):
    admin = Admin(
        id=2,
        user_id=50,
    )

    submission = VolunteerHour(
        id=20,
        student_id=stu.id,
        admin_id=admin.id,
        hours_logged=5,
        activity="Food Drive",
        activity_date=date(2026, 11, 1),
        organisation="UWI",
        status="Approved",
    )

    repo.get_admin_by_user_id.return_value = admin
    repo.get_submission_for_review.return_value = (
        submission,
        stu,
        "bob",
    )

    with pytest.raises(
        ValueError,
        match="already been reviewed",
    ):
        serv.review_hour_submission(
            submission_id=20,
            admin_user_id=50,
            decision="Approved",
            admin_notes="",
        )

    repo.save_submission_review.assert_not_called()

def test_student_can_redeem_reward_when_balance_is_enough(
    serv,
    repo,
    stu,
):
    reward = Reward(
        id=1,
        name="Bronze Badge",
        description="Bronze volunteer recognition badge",
        required_hours=10,
        category="Recognition",
    )

    repo.get_student_by_user_id.return_value = stu
    repo.get_reward_by_id.return_value = reward

    serv.get_dashboard_summary = MagicMock(
        return_value=StudentDashboardSummary(
            total_hours=13,
            rewards_balance=13,
            leaderboard_rank=1,
            milestones=[],
        )
    )

    repo.create_reward_redemption.return_value = MagicMock(
        redeemed_at=date(2026, 11, 1),
        status="Completed",
    )

    result = serv.redeem_reward(
        user_id=1,
        reward_id=1,
    )

    assert result.name == "Bronze Badge"
    assert result.status == "Completed"

    repo.create_reward_redemption.assert_called_once()


def test_student_cannot_redeem_reward_without_enough_balance(
    serv,
    repo,
    stu,
):
    reward = Reward(
        id=1,
        name="Bronze Badge",
        description="Bronze volunteer recognition badge",
        required_hours=10,
        category="Recognition",
    )

    repo.get_student_by_user_id.return_value = stu
    repo.get_reward_by_id.return_value = reward

    serv.get_dashboard_summary = MagicMock(
        return_value=StudentDashboardSummary(
            total_hours=8,
            rewards_balance=8,
            leaderboard_rank=1,
            milestones=[],
        )
    )

    with pytest.raises(
        ValueError,
        match="enough reward points",
    ):
        serv.redeem_reward(
            user_id=1,
            reward_id=1,
        )

    repo.create_reward_redemption.assert_not_called()