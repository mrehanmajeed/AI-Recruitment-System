from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import json

from database.connection import get_db
from database.models import JobDescription, Candidate
from services.pdf_parser import extract_text
from services.ai import parse_resume
from services.mailer import send_acknowledgment
from scheduler.jobs import score_candidate_by_id

router = APIRouter(prefix="/api")


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _as_list(value) -> list:
    return value if isinstance(value, list) else []

@router.post("/jobs")
def create_job(title: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    job = JobDescription(title=title, description=description)
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "title": job.title}

def _soft_delete_job(job_id: int, db: Session):
    job = (
        db.query(JobDescription)
        .filter(JobDescription.id == job_id, JobDescription.active == 1)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.active = 0
    db.commit()
    return {"message": "Job deleted"}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    try:
        return _soft_delete_job(job_id, db)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting job posting: {e}")


@router.post("/jobs/{job_id}/delete")
def delete_job_post(job_id: int, db: Session = Depends(get_db)):
    try:
        return _soft_delete_job(job_id, db)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting job posting: {e}")

@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobDescription).filter(JobDescription.active == 1).all()
    return jobs

@router.post("/upload-resume")
async def upload_resume(
    background_tasks: BackgroundTasks,
    job_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")
        
    try:
        pdf_bytes = await file.read()
        raw_text = extract_text(pdf_bytes)
        
        if not raw_text:
            raise HTTPException(status_code=422, detail="Could not extract text from PDF")
            
        parsed_data = parse_resume(raw_text)
        email = parsed_data.get("email")
        
        if not email:
            raise HTTPException(status_code=422, detail="Could not find email in resume")
            
        existing_candidate = db.query(Candidate).filter(Candidate.email == email, Candidate.job_id == job_id).first()
        if existing_candidate:
            return {"message": "Already applied"}
            
        job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        candidate = Candidate(
            job_id=job_id,
            name=parsed_data.get("name", ""),
            email=email,
            phone=parsed_data.get("phone", ""),
            resume_filename=file.filename,
            resume_raw_text=raw_text,
            parsed_experience_years=_as_float(parsed_data.get("total_experience_years")),
            parsed_skills=json.dumps(_as_list(parsed_data.get("skills"))),
            parsed_education=json.dumps(_as_list(parsed_data.get("education"))),
            parsed_current_role=parsed_data.get("current_role", ""),
            parsed_summary=parsed_data.get("summary", ""),
            status="pending_score"
        )
        
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        send_acknowledgment(candidate.name, candidate.email, job.title)
        
        candidate.ack_sent = 1
        db.commit()

        background_tasks.add_task(score_candidate_by_id, candidate.id)
        
        return {"message": "Application received", "candidate_id": candidate.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # simplified error handling for fallback
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/candidates/{cid}/rescore")
def rescore_candidate(
    cid: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    candidate = db.query(Candidate).filter(Candidate.id == cid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    candidate.status = "pending_score"
    candidate.ai_score = None
    candidate.ai_tier = None
    candidate.ai_reasoning = None
    candidate.ai_strengths = None
    candidate.ai_concerns = None
    candidate.ai_interview_questions = None
    candidate.error_log = None
    db.commit()
    background_tasks.add_task(score_candidate_by_id, candidate.id)
    return {"message": "Queued for rescoring"}


def _delete_candidate(cid: int, db: Session):
    candidate = db.query(Candidate).filter(Candidate.id == cid).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted"}


@router.delete("/candidates/{cid}")
def delete_candidate(cid: int, db: Session = Depends(get_db)):
    try:
        return _delete_candidate(cid, db)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting candidate: {e}")


@router.post("/candidates/{cid}/delete")
def delete_candidate_post(cid: int, db: Session = Depends(get_db)):
    try:
        return _delete_candidate(cid, db)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting candidate: {e}")
