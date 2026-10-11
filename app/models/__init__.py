"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.user import User
from app.models.student_awards import (
    Admin,
    Milestone,
    MilestoneProgress,
    Reward,
    RewardRedemption,
    Student,
    VolunteerHour,
)

__all__ = [
    "Admin",
    "Milestone",
    "MilestoneProgress",
    "Reward",
    "RewardRedemption",
    "Student",
    "User",
    "VolunteerHour",
]
