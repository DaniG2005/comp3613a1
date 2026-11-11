from fastapi import Response, status
from fastapi.responses import JSONResponse

from app.dependencies.auth import AuthDep, AdminDep
from app.dependencies.session import SessionDep
from app.repositories.user import UserRepository
from app.schemas.student_awards import (
    LoginRequest,
    RewardRedemptionCreate,
    VolunteerHourCreate,
    VolunteerHourReview,
)
from app.services.auth_service import AuthService
from app.services.student_awards import (
    SubmissionNotFoundError,
    get_rewards_page,
    get_volunteer_hours_for_user,
    log_volunteer_hours,
    redeem_reward,
    review_hour_submission,
)
from app.utilities.security import access_token_cookie_kwargs

from . import api_router

@api_router.post("/auth/login")
async def api_login(
    data: LoginRequest,
    response: Response,
    db: SessionDep,
):
    repo = UserRepository(db)
    serv = AuthService(repo)

    token = serv.authenticate_user(
        data.username,
        data.password,
    )

    if not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Incorrect username or password"
            },
        )

    user = repo.get_by_username(data.username)

    response.set_cookie(
        key="access_token",
        value=token,
        **access_token_cookie_kwargs(),
    )

    return {
        "message": "Login successful",
        "username": user.username,
        "role": user.role,
    }


@api_router.post(
    "/volunteer-hours",
    status_code=status.HTTP_201_CREATED,
)
async def api_log_volunteer_hours(
    data: VolunteerHourCreate,
    user: AuthDep,
    db: SessionDep,
):
    try:
        submission = log_volunteer_hours(
            db=db,
            user_id=user.id,
            hours_logged=data.hours_logged,
            activity=data.activity,
            activity_date=data.activity_date,
            organisation=data.organisation,
            student_notes=data.student_notes,
        )

        return {
            "id": submission.id,
            "student_id": submission.student_id,
            "hours_logged": submission.hours_logged,
            "activity": submission.activity,
            "activity_date": submission.activity_date.isoformat(),
            "organisation": submission.organisation,
            "student_notes": submission.student_notes,
            "status": submission.status,
        }

    except ValueError as error:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(error)},
        )


@api_router.get("/volunteer-hours")
async def api_get_volunteer_hours(
    user: AuthDep,
    db: SessionDep,
):
    return get_volunteer_hours_for_user(
        db=db,
        user_id=user.id,
    )

@api_router.patch("/volunteer-hours/{submission_id}")
async def api_review_volunteer_hours(
    submission_id: int,
    data: VolunteerHourReview,
    user: AdminDep,
    db: SessionDep,
):
    try:
        submission = review_hour_submission(
            db=db,
            submission_id=submission_id,
            admin_user_id=user.id,
            decision=data.decision,
            admin_notes=data.admin_notes,
        )

        return submission

    except SubmissionNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": str(error)},
        )

    except ValueError as error:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(error)},
        )


@api_router.get("/rewards")
async def api_get_rewards(
    user: AuthDep,
    db: SessionDep,
):
    try:
        return get_rewards_page(
            db=db,
            user_id=user.id,
        )

    except ValueError as error:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(error)},
        )


@api_router.post(
    "/reward-redemptions",
    status_code=status.HTTP_201_CREATED,
)
async def api_redeem_reward(
    data: RewardRedemptionCreate,
    user: AuthDep,
    db: SessionDep,
):
    try:
        return redeem_reward(
            db=db,
            user_id=user.id,
            reward_id=data.reward_id,
        )

    except ValueError as error:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(error)},
        )