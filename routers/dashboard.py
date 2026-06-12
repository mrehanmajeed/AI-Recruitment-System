from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
import os

from database.connection import get_db
from database.models import JobDescription, Candidate

router = APIRouter()

template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=template_dir)

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    jobs = db.query(JobDescription).filter(JobDescription.active == 1).all()
    
    total = len(candidates)
    pending = sum(1 for c in candidates if c.status in ["pending", "pending_score", "scoring"])
    invited = sum(1 for c in candidates if c.status == "invited")
    rejected = sum(1 for c in candidates if c.status == "rejected")
    error_count = sum(1 for c in candidates if c.status == "error")
    
    stats = {
        "total": total,
        "pending": pending,
        "invited": invited,
        "rejected": rejected,
        "error_count": error_count
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "candidates": candidates, 
        "jobs": jobs, 
        "stats": stats
    })

@router.get("/candidate/{cid}", response_class=HTMLResponse)
def candidate_detail(request: Request, cid: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == cid).first()
    if not candidate:
        return HTMLResponse("Candidate not found", status_code=404)
        
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
    
    skills = json.loads(candidate.parsed_skills or "[]")
    education = json.loads(candidate.parsed_education or "[]")
    strengths = json.loads(candidate.ai_strengths or "[]")
    concerns = json.loads(candidate.ai_concerns or "[]")
    questions = json.loads(candidate.ai_interview_questions or "[]")
    
    return templates.TemplateResponse("candidate_detail.html", {
        "request": request,
        "c": candidate,
        "job": job,
        "skills": skills,
        "education": education,
        "strengths": strengths,
        "concerns": concerns,
        "questions": questions
    })

@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request, db: Session = Depends(get_db)):
    jobs = db.query(JobDescription).filter(JobDescription.active == 1).all()
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "jobs": jobs
    })
