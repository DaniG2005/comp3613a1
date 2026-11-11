from datetime import date

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class VolunteerHourCreate(BaseModel):
    hours_logged: int
    activity: str
    activity_date: date
    organisation: str
    student_notes: str = ""


class VolunteerHourReview(BaseModel):
    decision: str
    admin_notes: str = ""


class RewardRedemptionCreate(BaseModel):
    reward_id: int