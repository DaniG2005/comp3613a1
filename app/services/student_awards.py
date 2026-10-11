from datetime import date, datetime
from dataclasses import dataclass

from sqlmodel import Session

from app.models.student_awards import VolunteerHour
from app.repositories.student_awards import StudentAwardsRepository


@dataclass(frozen=True)
class MilestoneStatus:
    name: str
    required_hours: int
    progress_percent: int
    unlocked: bool
    hours_remaining: int


@dataclass(frozen=True)
class StudentDashboardSummary:
    total_hours: int
    rewards_balance: int
    leaderboard_rank: int
    milestones: list[MilestoneStatus]


@dataclass(frozen=True)
class LeaderboardEntry:
    rank: int
    display_name: str
    approved_hours: int
    is_current_student: bool


@dataclass(frozen=True)
class ClaimedRewardEntry:
    name: str
    description: str
    category: str
    redeemed_at: date
    status: str


@dataclass(frozen=True)
class AvailableRewardEntry:
    id: int
    name: str
    description: str
    category: str
    required_hours: int


@dataclass(frozen=True)
class RewardsPageData:
    rewards_balance: int
    available_rewards: list[AvailableRewardEntry]
    claimed_rewards: list[ClaimedRewardEntry]


@dataclass(frozen=True)
class PendingHourEntry:
    id: int
    student_name: str
    username: str
    activity: str
    activity_date: date
    hours_logged: int
    submitted_at: datetime


@dataclass(frozen=True)
class HourReviewDetails:
    id: int
    student_name: str
    username: str
    activity: str
    activity_date: date
    organisation: str
    hours_logged: int
    student_notes: str | None
    submitted_at: datetime
    current_approved_hours: int


class SubmissionNotFoundError(LookupError):
    pass


class StudentAwardsService:
    def __init__(self, repository: StudentAwardsRepository):
        self.repository = repository

    def log_volunteer_hours(
        self,
        *,
        user_id: int,
        hours_logged: int,
        activity: str,
        activity_date: date,
        organisation: str,
        student_notes: str,
    ) -> VolunteerHour:
        if hours_logged <= 0:
            raise ValueError("Hours logged must be a positive integer.")

        student = self.repository.get_student_by_user_id(user_id)

        if student is None:
            raise ValueError("Your student profile is not set up yet.")
        if student.id is None:
            raise RuntimeError("The student profile has not been saved.")

        submission = VolunteerHour(
            student_id=student.id,
            hours_logged=hours_logged,
            activity=activity,
            activity_date=activity_date,
            organisation=organisation,
            student_notes=student_notes or None,
        )

        return self.repository.create_volunteer_hour(submission)

    def get_volunteer_hours_for_user(self, user_id: int) -> list[VolunteerHour]:
        student = self.repository.get_student_by_user_id(user_id)
        if student is None:
            return []
        if student.id is None:
            raise RuntimeError("The student profile has not been saved.")
        return self.repository.get_volunteer_hours_for_student(student.id)

    def get_dashboard_summary(self, user_id: int) -> StudentDashboardSummary:
        student = self.repository.get_student_by_user_id(user_id)
        if student is None or student.id is None:
            raise ValueError("Your student profile is not set up yet.")

        approved_hours_by_student = self.repository.get_approved_hours_by_student()
        total_hours = approved_hours_by_student.get(student.id, 0)
        rewards_balance = (
            total_hours - self.repository.get_redeemed_reward_hours(student.id)
        )
        leaderboard_rank = 1 + sum(
            hours > total_hours
            for other_student_id, hours in approved_hours_by_student.items()
            if other_student_id != student.id
        )
        milestones = self.repository.get_milestones()
        unlocked_progress = {
            progress.milestone_id: progress
            for progress in self.repository.get_milestone_progress(student.id)
            if progress.unlocked
        }
        milestone_statuses: list[MilestoneStatus] = []
        today = date.today()
        for milestone in milestones:
            if milestone.id is None:
                raise RuntimeError("A milestone has not been saved.")
            unlocked = total_hours >= milestone.required_hours
            if unlocked:
                if milestone.id not in unlocked_progress:
                    self.repository.unlock_milestone(
                        student_id=student.id,
                        milestone_id=milestone.id,
                        unlocked_at=today,
                    )
                progress_percent = 100
            else:
                progress_percent = min(
                    100,
                    int(total_hours / milestone.required_hours * 100),
                )
            milestone_statuses.append(
                MilestoneStatus(
                    name=milestone.name,
                    required_hours=milestone.required_hours,
                    progress_percent=progress_percent,
                    unlocked=unlocked,
                    hours_remaining=max(0, milestone.required_hours - total_hours),
                )
            )

        return StudentDashboardSummary(
            total_hours=total_hours,
            rewards_balance=rewards_balance,
            leaderboard_rank=leaderboard_rank,
            milestones=milestone_statuses,
        )

    def get_leaderboard(self, user_id: int) -> list[LeaderboardEntry]:
        current_student = self.repository.get_student_by_user_id(user_id)
        if current_student is None or current_student.id is None:
            raise ValueError("Your student profile is not set up yet.")

        rows = sorted(
            self.repository.get_leaderboard_rows(),
            key=lambda row: (-row[2], row[1].casefold()),
        )
        entries: list[LeaderboardEntry] = []
        previous_hours: int | None = None
        current_rank = 0
        for position, (student, username, approved_hours) in enumerate(rows, start=1):
            if approved_hours != previous_hours:
                current_rank = position
                previous_hours = approved_hours
            entries.append(
                LeaderboardEntry(
                    rank=current_rank,
                    display_name=f"{student.first_name} {student.last_name}",
                    approved_hours=approved_hours,
                    is_current_student=student.id == current_student.id,
                )
            )
        return entries

    def get_claimed_rewards(self, user_id: int) -> list[ClaimedRewardEntry]:
        student = self.repository.get_student_by_user_id(user_id)
        if student is None or student.id is None:
            raise ValueError("Your student profile is not set up yet.")

        return [
            ClaimedRewardEntry(
                name=reward.name,
                description=reward.description,
                category=reward.category,
                redeemed_at=redemption.redeemed_at,
                status=redemption.status,
            )
            for redemption, reward in self.repository.get_claimed_rewards(student.id)
        ]

    def get_rewards_page(self, user_id: int) -> RewardsPageData:
        summary = self.get_dashboard_summary(user_id)
        claimed_rewards = self.get_claimed_rewards(user_id)
        available_rewards = []
        for reward in self.repository.get_rewards():
            if reward.id is None:
                raise RuntimeError("A reward has not been saved.")
            if reward.required_hours <= summary.rewards_balance:
                available_rewards.append(
                    AvailableRewardEntry(
                        id=reward.id,
                        name=reward.name,
                        description=reward.description,
                        category=reward.category,
                        required_hours=reward.required_hours,
                    )
                )
        return RewardsPageData(
            rewards_balance=summary.rewards_balance,
            available_rewards=available_rewards,
            claimed_rewards=claimed_rewards,
        )

    def redeem_reward(self, *, user_id: int, reward_id: int) -> ClaimedRewardEntry:
        student = self.repository.get_student_by_user_id(user_id)
        if student is None or student.id is None:
            raise ValueError("Your student profile is not set up yet.")

        reward = self.repository.get_reward_by_id(reward_id)
        if reward is None:
            raise ValueError("That reward could not be found.")

        summary = self.get_dashboard_summary(user_id)
        if reward.required_hours > summary.rewards_balance:
            raise ValueError("You do not have enough reward points for this reward.")

        redemption = self.repository.create_reward_redemption(
            student_id=student.id,
            reward_id=reward.id,
            redeemed_at=date.today(),
        )
        return ClaimedRewardEntry(
            name=reward.name,
            description=reward.description,
            category=reward.category,
            redeemed_at=redemption.redeemed_at,
            status=redemption.status,
        )

    def create_student_profile(
        self, *, user_id: int, first_name: str, last_name: str
    ) -> None:
        self.repository.create_student(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )

    def get_pending_hours(self) -> list[PendingHourEntry]:
        pending_entries = []
        for submission, student, username in self.repository.get_pending_submissions():
            if submission.id is None:
                raise RuntimeError("A volunteer-hour submission has not been saved.")
            pending_entries.append(
                PendingHourEntry(
                    id=submission.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    username=username,
                    activity=submission.activity,
                    activity_date=submission.activity_date,
                    hours_logged=submission.hours_logged,
                    submitted_at=submission.submitted_at,
                )
            )
        return pending_entries

    def get_hour_review(self, submission_id: int) -> HourReviewDetails:
        result = self.repository.get_submission_for_review(submission_id)
        if result is None:
            raise SubmissionNotFoundError("Volunteer-hour submission not found.")
        submission, student, username = result
        if submission.id is None or student.id is None:
            raise RuntimeError("The submission or student profile has not been saved.")
        return HourReviewDetails(
            id=submission.id,
            student_name=f"{student.first_name} {student.last_name}",
            username=username,
            activity=submission.activity,
            activity_date=submission.activity_date,
            organisation=submission.organisation,
            hours_logged=submission.hours_logged,
            student_notes=submission.student_notes,
            submitted_at=submission.submitted_at,
            current_approved_hours=self.repository.get_approved_hours_for_student(
                student.id
            ),
        )

    def review_hour_submission(
        self,
        *,
        submission_id: int,
        admin_user_id: int,
        decision: str,
        admin_notes: str,
    ) -> VolunteerHour:
        if decision not in {"Approved", "Rejected"}:
            raise ValueError("Choose approve or reject for this submission.")
        if decision == "Rejected" and not admin_notes.strip():
            raise ValueError("Admin notes are required when rejecting a submission.")

        admin = self.repository.get_admin_by_user_id(admin_user_id)
        if admin is None or admin.id is None:
            raise ValueError("The admin profile is not set up.")
        result = self.repository.get_submission_for_review(submission_id)
        if result is None:
            raise SubmissionNotFoundError("Volunteer-hour submission not found.")
        submission, _, _ = result
        if submission.status != "Pending":
            raise ValueError("This submission has already been reviewed.")
        return self.repository.save_submission_review(
            submission=submission,
            admin_id=admin.id,
            decision=decision,
            admin_notes=admin_notes.strip(),
        )


def log_volunteer_hours(
    *,
    db: Session,
    user_id: int,
    hours_logged: int,
    activity: str,
    activity_date: date,
    organisation: str,
    student_notes: str,
) -> VolunteerHour:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.log_volunteer_hours(
        user_id=user_id,
        hours_logged=hours_logged,
        activity=activity,
        activity_date=activity_date,
        organisation=organisation,
        student_notes=student_notes,
    )


def get_volunteer_hours_for_user(*, db: Session, user_id: int) -> list[VolunteerHour]:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_volunteer_hours_for_user(user_id)


def get_student_dashboard_summary(
    *, db: Session, user_id: int
) -> StudentDashboardSummary:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_dashboard_summary(user_id)


def get_leaderboard(
    *, db: Session, user_id: int
) -> list[LeaderboardEntry]:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_leaderboard(user_id)


def get_claimed_rewards(
    *, db: Session, user_id: int
) -> list[ClaimedRewardEntry]:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_claimed_rewards(user_id)


def get_rewards_page(*, db: Session, user_id: int) -> RewardsPageData:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_rewards_page(user_id)


def redeem_reward(*, db: Session, user_id: int, reward_id: int) -> ClaimedRewardEntry:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.redeem_reward(user_id=user_id, reward_id=reward_id)


def create_student_profile(
    *,
    db: Session,
    user_id: int,
    first_name: str,
    last_name: str,
) -> None:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    service.create_student_profile(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
    )


def get_pending_hours(*, db: Session) -> list[PendingHourEntry]:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_pending_hours()


def get_hour_review(*, db: Session, submission_id: int) -> HourReviewDetails:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.get_hour_review(submission_id)


def review_hour_submission(
    *,
    db: Session,
    submission_id: int,
    admin_user_id: int,
    decision: str,
    admin_notes: str,
) -> VolunteerHour:
    repository = StudentAwardsRepository(db)
    service = StudentAwardsService(repository)
    return service.review_hour_submission(
        submission_id=submission_id,
        admin_user_id=admin_user_id,
        decision=decision,
        admin_notes=admin_notes,
    )
