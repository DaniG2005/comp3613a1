from datetime import date

from fastapi import Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.services.student_awards import (
    get_leaderboard,
    get_rewards_page,
    get_student_dashboard_summary,
    get_volunteer_hours_for_user,
    log_volunteer_hours,
    redeem_reward,
)
from app.utilities.flash import flash
from . import router, templates


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    submissions = get_volunteer_hours_for_user(db=db, user_id=user.id)
    summary = get_student_dashboard_summary(db=db, user_id=user.id)
    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={
            "user": user,
            "submissions": submissions,
            "summary": summary,
        }
    )


@router.get("/app/log-hours", response_class=HTMLResponse, name="log_hours_view")
async def log_hours_view(request: Request, user: AuthDep):
    return templates.TemplateResponse(
        request=request,
        name="log-hours.html",
        context={"user": user},
    )


@router.get("/app/leaderboard", response_class=HTMLResponse, name="leaderboard_view")
async def leaderboard_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    entries = get_leaderboard(db=db, user_id=user.id)
    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={"user": user, "entries": entries},
    )


@router.get("/app/rewards", response_class=HTMLResponse, name="rewards_view")
async def rewards_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    rewards_page = get_rewards_page(db=db, user_id=user.id)
    return templates.TemplateResponse(
        request=request,
        name="rewards.html",
        context={
            "user": user,
            "rewards_balance": rewards_page.rewards_balance,
            "available_rewards": rewards_page.available_rewards,
            "claimed_rewards": rewards_page.claimed_rewards,
        },
    )


@router.post("/app/rewards/claim", name="claim_reward")
async def claim_reward(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    reward_id: int = Form(),
):
    try:
        claimed = redeem_reward(db=db, user_id=user.id, reward_id=reward_id)
        flash(request, f"{claimed.name} claimed successfully. Points were deducted.")
    except ValueError as error:
        flash(request, str(error), "danger")
    return RedirectResponse(
        url=request.url_for("rewards_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/app/hours", response_class=HTMLResponse)
async def submit_volunteer_hours(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    hours_logged: int = Form(),
    activity: str = Form(min_length=1),
    activity_date: date = Form(),
    organisation: str = Form(min_length=1),
    student_notes: str = Form(default=""),
):
    try:
        log_volunteer_hours(
            db=db,
            user_id=user.id,
            hours_logged=hours_logged,
            activity=activity,
            activity_date=activity_date,
            organisation=organisation,
            student_notes=student_notes
        )
        flash(request, "Volunteer hours submitted and are pending review.")
        return RedirectResponse(url="/app", status_code=303)
    except ValueError as error:
        return templates.TemplateResponse(
            request=request,
            name="log-hours.html",
            context={
                "user": user,
                "error_message": str(error),
            },
            status_code=400
        )