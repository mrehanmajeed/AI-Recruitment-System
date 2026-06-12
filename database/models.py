from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    candidates = relationship("Candidate", back_populates="job")

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"))
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(50), nullable=True)
    resume_filename = Column(String(255))
    resume_raw_text = Column(Text)
    parsed_experience_years = Column(Float, default=0.0)
    parsed_skills = Column(Text)
    parsed_education = Column(Text)
    parsed_current_role = Column(String(255))
    parsed_summary = Column(Text)
    ai_score = Column(Float, nullable=True)
    ai_tier = Column(String(20), nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    ai_strengths = Column(Text, nullable=True)
    ai_concerns = Column(Text, nullable=True)
    ai_interview_questions = Column(Text, nullable=True)
    ack_sent = Column(Integer, default=0)
    decision_sent = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    error_log = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    job = relationship("JobDescription", back_populates="candidates")
