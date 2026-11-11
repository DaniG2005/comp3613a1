from datetime import date

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.models.user import User
from app.models.student_awards import Reward
from app.repositories.student_awards import StudentAwardsRepository
from app.services.student_awards import StudentAwardsService

@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def repo(db):
    return StudentAwardsRepository(db)


@pytest.fixture
def serv(repo):
    return StudentAwardsService(repo)

@pytest.fixture
def stu(db, repo):
    user = User(
        username="teststudent",
        email="student@test.com",
        password="testpass",
        role="regular_user",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return repo.create_student(
        user_id=user.id,
        first_name="Test",
        last_name="Student",
    )

@pytest.fixture
def admin(db, repo):
    user = User(
        username="testadmin",
        email="admin@test.com",
        password="testpass",
        role="admin",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return repo.create_admin_profile(
        user_id=user.id
    )

def test_student_logs_volunteer_hours(
    serv,
    repo,
    stu,
):
    result = serv.log_volunteer_hours(
        user_id=stu.user_id,
        hours_logged=5,
        activity="Food Drive",
        activity_date=date(2026, 11, 1),
        organisation="UWI",
        student_notes="Helped distribute food.",
    )

    saved = repo.get_volunteer_hours_for_student(stu.id)

    assert result.id is not None
    assert result.status == "Pending"

    assert len(saved) == 1
    assert saved[0].hours_logged == 5
    assert saved[0].activity == "Food Drive"
    assert saved[0].student_id == stu.id


def test_admin_approves_volunteer_hours(
    serv,
    repo,
    stu,
    admin,
):
    submission = serv.log_volunteer_hours(
        user_id=stu.user_id,
        hours_logged=5,
        activity="Beach Cleanup",
        activity_date=date(2026, 11, 2),
        organisation="UWI",
        student_notes="Collected waste.",
    )

    result = serv.review_hour_submission(
        submission_id=submission.id,
        admin_user_id=admin.user_id,
        decision="Approved",
        admin_notes="Verified.",
    )

    saved, _, _ = repo.get_submission_for_review(
        submission.id
    )

    approved_hours = repo.get_approved_hours_for_student(
        stu.id
    )

    assert result.status == "Approved"
    assert saved.status == "Approved"
    assert saved.admin_id == admin.id
    assert saved.admin_notes == "Verified."
    assert approved_hours == 5


def test_student_redeems_reward(
    db,
    serv,
    repo,
    stu,
    admin,
):
    submission = serv.log_volunteer_hours(
        user_id=stu.user_id,
        hours_logged=12,
        activity="Community Service",
        activity_date=date(2026, 11, 3),
        organisation="UWI",
        student_notes="Completed volunteer work.",
    )

    serv.review_hour_submission(
        submission_id=submission.id,
        admin_user_id=admin.user_id,
        decision="Approved",
        admin_notes="Approved.",
    )

    reward = Reward(
        name="Bronze Badge",
        description="Bronze volunteer recognition badge",
        required_hours=10,
        category="Recognition",
    )

    db.add(reward)
    db.commit()
    db.refresh(reward)

    result = serv.redeem_reward(
        user_id=stu.user_id,
        reward_id=reward.id,
    )

    claimed = repo.get_claimed_rewards(stu.id)

    summary = serv.get_dashboard_summary(
        stu.user_id
    )

    assert result.name == "Bronze Badge"
    assert result.status == "Completed"

    assert len(claimed) == 1
    assert claimed[0][1].name == "Bronze Badge"

    assert summary.rewards_balance == 2  