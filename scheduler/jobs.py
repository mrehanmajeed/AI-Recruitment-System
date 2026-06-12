import logging
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database.connection import SessionLocal
from database.models import Candidate, JobDescription
from services.ai import score_candidate, generate_rejection_body
from services.mailer import send_interview_invite, send_interviewer_brief, send_rejection
from config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _score_candidate(candidate: Candidate, db):
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
    if not job:
        candidate.status = "error"
        candidate.error_log = "Job posting not found for candidate"
        db.commit()
        return

    candidate.status = "scoring"
    candidate.error_log = None
    db.commit()

    candidate_data_dict = {
        "name": candidate.name,
        "parsed_experience_years": candidate.parsed_experience_years,
        "parsed_current_role": candidate.parsed_current_role,
        "parsed_skills": candidate.parsed_skills,
        "parsed_education": candidate.parsed_education
    }

    score_result = score_candidate(candidate_data_dict, job.description)

    candidate.ai_score = score_result.get("score")
    candidate.ai_tier = score_result.get("tier")
    candidate.ai_reasoning = score_result.get("reasoning")
    candidate.ai_strengths = json.dumps(score_result.get("strengths", []))
    candidate.ai_concerns = json.dumps(score_result.get("concerns", []))
    candidate.ai_interview_questions = json.dumps(score_result.get("interview_questions", []))

    if candidate.ai_score is not None and candidate.ai_score >= settings.SCORE_THRESHOLD:
        send_interview_invite(candidate.name, candidate.email, job.title, settings.CALENDLY_LINK)

        strengths = score_result.get("strengths", [])
        concerns = score_result.get("concerns", [])
        questions = score_result.get("interview_questions", [])

        send_interviewer_brief(
            settings.HR_EMAIL, candidate.name, job.title,
            candidate.ai_score, strengths, concerns, questions
        )
        candidate.status = "invited"
    else:
        strengths_list = score_result.get("strengths", [])
        strength = strengths_list[0] if strengths_list else "your background"
        rejection_body = generate_rejection_body(candidate.name, job.title, strength)
        send_rejection(candidate.name, candidate.email, job.title, rejection_body)
        candidate.status = "rejected"

    candidate.decision_sent = 1
    db.commit()


def score_candidate_by_id(candidate_id: int):
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            logger.warning("Candidate %s not found for scoring", candidate_id)
            return

        _score_candidate(candidate, db)
    except Exception as e:
        logger.error(f"Error scoring candidate {candidate_id}: {e}")
        if "candidate" in locals() and candidate:
            candidate.status = "error"
            candidate.error_log = str(e)
            db.commit()
    finally:
        db.close()


def score_pending_candidates():
    db = SessionLocal()
    try:
        pending_candidates = db.query(Candidate).filter(Candidate.status == "pending_score").all()
        for candidate in pending_candidates:
            try:
                _score_candidate(candidate, db)
            except Exception as e:
                logger.error(f"Error scoring candidate {candidate.id}: {e}")
                candidate.status = "error"
                candidate.error_log = str(e)
                db.commit()
    except Exception as e:
        logger.error(f"Error in score_pending_candidates job: {e}")
    finally:
        db.close()

def start_scheduler():
    if scheduler.running:
        logger.info("Scheduler already running.")
        return

    scheduler.add_job(
        score_pending_candidates,
        trigger=IntervalTrigger(minutes=1),
        id="score_candidates",
        next_run_time=datetime.now(),
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started.")
