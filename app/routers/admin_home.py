from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.dependencies.session import SessionDep
from app.dependencies.auth import AdminDep
from app.services.student_awards import (
    SubmissionNotFoundError,
    get_hour_review,
    get_pending_hours,
    review_hour_submission,
)
from app.utilities.flash import flash
from . import router, templates


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
):
    pending_submissions = get_pending_hours(db=db)
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "pending_submissions": pending_submissions,
        },
    )


@router.get(
    "/admin/volunteer-hours/{submission_id}",
    response_class=HTMLResponse,
    name="review_volunteer_hour_view",
)
async def review_volunteer_hour_view(
    request: Request,
    submission_id: int,
    user: AdminDep,
    db: SessionDep,
):
    try:
        details = get_hour_review(db=db, submission_id=submission_id)
    except SubmissionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return templates.TemplateResponse(
        request=request,
        name="admin-review.html",
        context={"user": user, "submission": details},
    )


@router.post(
    "/admin/volunteer-hours/{submission_id}/review",
    name="review_volunteer_hour",
)
async def review_volunteer_hour(
    request: Request,
    submission_id: int,
    user: AdminDep,
    db: SessionDep,
    decision: str = Form(),
    admin_notes: str = Form(default=""),
):
    # STUDENT ROUTE SNIPPET START
    # Complete this thin action handler for Approve / Reject.
    try:
        reviewed_submission = review_hour_submission(
            db=db,
            submission_id=submission_id,
            admin_user_id=user.id,
            decision=decision,
            admin_notes=admin_notes,
        )
        if reviewed_submission.status == "Approved":
            flash(request, "Volunteer hour submission approved successfully.", "success")
        else:
            flash(request, "Volunteer hour submission rejected successfully.", "success")

        return RedirectResponse(
            url="/admin",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except SubmissionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    except ValueError as error:
        flash(request, str(error), "danger")

        return RedirectResponse(
            url=request.url_for(
                "review_volunteer_hour_view", submission_id=submission_id
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
