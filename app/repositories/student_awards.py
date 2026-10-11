from datetime import date, datetime

from sqlmodel import Session, func, select

from app.models.student_awards import (
    Admin,
    Milestone,
    MilestoneProgress,
    Reward,
    RewardRedemption,
    Student,
    VolunteerHour,
)
from app.models.user import User


class StudentAwardsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_student_by_user_id(self, user_id: int) -> Student | None:
        # STUDENT SNIPPET START
        statement = select(Student).where(Student.user_id == user_id)
        return self.db.exec(statement).first()
        # STUDENT SNIPPET END

    def create_volunteer_hour(self, submission: VolunteerHour) -> VolunteerHour:
        try:
            self.db.add(submission)
            self.db.commit()
            self.db.refresh(submission)
            return submission
        except Exception:
            self.db.rollback()
            raise

    def get_volunteer_hours_for_student(self, student_id: int) -> list[VolunteerHour]:
        statement = (
            select(VolunteerHour)
            .where(VolunteerHour.student_id == student_id)
            .order_by(VolunteerHour.submitted_at.desc())
        )
        return list(self.db.exec(statement).all())

    def get_admin_by_user_id(self, user_id: int) -> Admin | None:
        statement = select(Admin).where(Admin.user_id == user_id)
        return self.db.exec(statement).first()

    def get_pending_submissions(self) -> list[tuple[VolunteerHour, Student, str]]:
        statement = (
            select(VolunteerHour, Student, User.username)
            .join(Student, VolunteerHour.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(VolunteerHour.status == "Pending")
            .order_by(VolunteerHour.submitted_at.asc())
        )
        return list(self.db.exec(statement).all())

    def get_submission_for_review(
        self, submission_id: int
    ) -> tuple[VolunteerHour, Student, str] | None:
        statement = (
            select(VolunteerHour, Student, User.username)
            .join(Student, VolunteerHour.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(VolunteerHour.id == submission_id)
        )
        return self.db.exec(statement).first()

    def save_submission_review(
        self,
        *,
        submission: VolunteerHour,
        admin_id: int,
        decision: str,
        admin_notes: str,
    ) -> VolunteerHour:
        try:
            submission.admin_id = admin_id
            submission.status = decision
            submission.admin_notes = admin_notes or None
            submission.approved_at = datetime.utcnow() if decision == "Approved" else None
            self.db.add(submission)
            self.db.commit()
            self.db.refresh(submission)
            return submission
        except Exception:
            self.db.rollback()
            raise

    def get_approved_hours_for_student(self, student_id: int) -> int:
        statement = select(
            func.coalesce(func.sum(VolunteerHour.hours_logged), 0)
        ).where(
            VolunteerHour.student_id == student_id,
            VolunteerHour.status == "Approved",
        )
        return int(self.db.exec(statement).one())

    def get_approved_hours_by_student(self) -> dict[int, int]:
        statement = (
            select(VolunteerHour.student_id, func.sum(VolunteerHour.hours_logged))
            .where(VolunteerHour.status == "Approved")
            .group_by(VolunteerHour.student_id)
        )
        return {
            student_id: int(hours or 0)
            for student_id, hours in self.db.exec(statement).all()
        }

    def get_leaderboard_rows(self) -> list[tuple[Student, str, int]]:
        statement = (
            select(
                Student,
                User.username,
                func.coalesce(func.sum(VolunteerHour.hours_logged), 0),
            )
            .join(User, Student.user_id == User.id)
            .outerjoin(
                VolunteerHour,
                (VolunteerHour.student_id == Student.id)
                & (VolunteerHour.status == "Approved"),
            )
            .where(Student.is_active.is_(True))
            .group_by(Student.id, User.username)
        )
        return [
            (student, username, int(approved_hours or 0))
            for student, username, approved_hours in self.db.exec(statement).all()
        ]

    def get_redeemed_reward_hours(self, student_id: int) -> int:
        statement = (
            select(func.coalesce(func.sum(Reward.required_hours), 0))
            .select_from(RewardRedemption)
            .join(Reward, RewardRedemption.reward_id == Reward.id)
            .where(
                RewardRedemption.student_id == student_id,
                RewardRedemption.status.in_(("Approved", "Completed")),
            )
        )
        return int(self.db.exec(statement).one())

    def get_rewards(self) -> list[Reward]:
        statement = select(Reward).order_by(Reward.required_hours, Reward.name)
        return list(self.db.exec(statement).all())

    def get_reward_by_id(self, reward_id: int) -> Reward | None:
        return self.db.get(Reward, reward_id)

    def create_reward_redemption(
        self, *, student_id: int, reward_id: int, redeemed_at: date
    ) -> RewardRedemption:
        redemption = RewardRedemption(
            student_id=student_id,
            reward_id=reward_id,
            redeemed_at=redeemed_at,
            status="Completed",
        )
        try:
            self.db.add(redemption)
            self.db.commit()
            self.db.refresh(redemption)
            return redemption
        except Exception:
            self.db.rollback()
            raise

    def get_claimed_rewards(
        self, student_id: int
    ) -> list[tuple[RewardRedemption, Reward]]:
        statement = (
            select(RewardRedemption, Reward)
            .join(Reward, RewardRedemption.reward_id == Reward.id)
            .where(RewardRedemption.student_id == student_id)
            .order_by(RewardRedemption.redeemed_at.desc(), RewardRedemption.id.desc())
        )
        return list(self.db.exec(statement).all())

    def get_milestones(self) -> list[Milestone]:
        return list(
            self.db.exec(select(Milestone).order_by(Milestone.required_hours)).all()
        )

    def get_milestone_progress(self, student_id: int) -> list[MilestoneProgress]:
        statement = select(MilestoneProgress).where(
            MilestoneProgress.student_id == student_id
        )
        return list(self.db.exec(statement).all())

    def unlock_milestone(
        self, *, student_id: int, milestone_id: int, unlocked_at: date
    ) -> None:
        statement = select(MilestoneProgress).where(
            MilestoneProgress.student_id == student_id,
            MilestoneProgress.milestone_id == milestone_id,
        )
        progress = self.db.exec(statement).first()
        if progress is None:
            progress = MilestoneProgress(
                student_id=student_id,
                milestone_id=milestone_id,
                unlocked=True,
                unlocked_at=unlocked_at,
            )
        else:
            progress.unlocked = True
            progress.unlocked_at = progress.unlocked_at or unlocked_at
        try:
            self.db.add(progress)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def ensure_default_award_catalog(self) -> None:
        milestone_defaults = (
            ("Bronze Badge", 10, "Awarded for 10 approved volunteer hours."),
            ("Department Mug", 25, "Department mug milestone at 25 approved hours."),
            ("Department Shirt", 50, "Department shirt milestone at 50 approved hours."),
        )
        reward_defaults = (
            ("Bronze Badge", 10, "Bronze volunteer recognition badge", "Recognition"),
            ("Department Mug", 25, "Department mug", "Merchandise"),
            ("Department Shirt", 50, "Department shirt", "Merchandise"),
        )
        try:
            existing = {
                milestone.name: milestone
                for milestone in self.db.exec(select(Milestone)).all()
            }
            for name, required_hours, description in milestone_defaults:
                if name not in existing:
                    self.db.add(
                        Milestone(
                            name=name,
                            required_hours=required_hours,
                            description=description,
                        )
                    )
            existing_rewards = {
                reward.name: reward for reward in self.db.exec(select(Reward)).all()
            }
            for name, required_hours, description, category in reward_defaults:
                if name not in existing_rewards:
                    self.db.add(
                        Reward(
                            name=name,
                            required_hours=required_hours,
                            description=description,
                            category=category,
                        )
                    )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def create_student(
        self, *, user_id: int, first_name: str, last_name: str
    ) -> Student:
        student = Student(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )
        try:
            self.db.add(student)
            self.db.commit()
            self.db.refresh(student)
            return student
        except Exception:
            self.db.rollback()
            raise

    def create_admin_profile(self, *, user_id: int) -> Admin:
        admin = Admin(user_id=user_id)
        try:
            self.db.add(admin)
            self.db.commit()
            self.db.refresh(admin)
            return admin
        except Exception:
            self.db.rollback()
            raise
