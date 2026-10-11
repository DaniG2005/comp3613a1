from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    first_name: str
    last_name: str
    total_hours: int = 0
    is_active: bool = True


class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)


class Milestone(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    required_hours: int
    description: str


class MilestoneProgress(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("student_id", "milestone_id", name="uq_student_milestone"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    milestone_id: int = Field(foreign_key="milestone.id", index=True)
    unlocked: bool = False
    unlocked_at: Optional[date] = Field(default=None)


class Reward(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    required_hours: int
    category: str


class RewardRedemption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # STUDENT SNIPPET START
    student_id: int = Field(foreign_key="student.id", index=True)
    reward_id: int = Field(foreign_key="reward.id", index=True)
    redeemed_at: date = Field(default_factory=date.today)
    status: str = Field(default="Completed")
    # STUDENT SNIPPET END


class VolunteerHour(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # STUDENT SNIPPET START
    student_id: int = Field(foreign_key="student.id", index=True)
    hours_logged: int
    activity: str
    activity_date: date
    organisation: str
    student_notes: Optional[str] = Field(default=None)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    # STUDENT REVIEW SNIPPET START
    # Complete the review fields: reviewer, status, approval time, and admin notes.
    admin_id: Optional[int] = Field(foreign_key="admin.id", default=None, index=True)
    status: str = Field(default="Pending")
    approved_at: Optional[datetime] = Field(default=None)
    admin_notes: Optional[str] = Field(default=None)
    # STUDENT REVIEW SNIPPET END
    # STUDENT SNIPPET END
