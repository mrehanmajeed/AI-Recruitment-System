import google.generativeai as genai
import json
import logging
import re
from config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel(settings.GEMINI_MODEL)

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])([A-Z0-9._%+-]+(?:\s*\[at\]\s*|\s*@\s*)[A-Z0-9.-]+(?:\s*\[dot\]\s*|\s*\.\s*)[A-Z]{2,})(?![\w.-])",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}"
)


def _normalize_email(raw_email: str) -> str:
    email = raw_email.lower()
    email = re.sub(r"\s*\[at\]\s*", "@", email)
    email = re.sub(r"\s*\[dot\]\s*", ".", email)
    email = re.sub(r"\s+", "", email)
    return email.strip(".,;:()<>[]{}")


def extract_contact_info(resume_text: str) -> dict:
    email_match = EMAIL_PATTERN.search(resume_text or "")
    phone_match = PHONE_PATTERN.search(resume_text or "")

    return {
        "email": _normalize_email(email_match.group(1)) if email_match else "",
        "phone": phone_match.group(0).strip() if phone_match else "",
    }


def _guess_name(resume_text: str) -> str:
    for line in (resume_text or "").splitlines()[:12]:
        value = line.strip()
        if not value or EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
            continue
        if any(token in value.lower() for token in ["resume", "curriculum vitae", "linkedin", "github", "portfolio"]):
            continue
        words = value.split()
        if 1 < len(words) <= 5 and all(any(ch.isalpha() for ch in word) for word in words):
            return value
    return ""


def _parse_json_response(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise

def parse_resume(resume_text: str) -> dict:
    contact_info = extract_contact_info(resume_text)
    prompt = f"""Extract structured information from this resume. Return ONLY a valid JSON object
with NO explanation, no markdown, no code fences.
Schema:
{{
  "name": "",
  "email": "",
  "phone": "",
  "total_experience_years": 0,
  "current_role": "",
  "skills": [],
  "education": [{{"degree": "", "institution": "", "year": ""}}],
  "summary": ""
}}
Resume text: {resume_text[:4000]}"""
    try:
        response = model.generate_content(prompt)
        parsed = _parse_json_response(response.text)
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        parsed = {}

    parsed["email"] = contact_info["email"] or _normalize_email(str(parsed.get("email", "")))
    parsed["phone"] = contact_info["phone"] or str(parsed.get("phone", "")).strip()
    parsed["name"] = str(parsed.get("name", "")).strip() or _guess_name(resume_text)
    parsed.setdefault("total_experience_years", 0)
    parsed.setdefault("current_role", "")
    parsed.setdefault("skills", [])
    parsed.setdefault("education", [])
    parsed.setdefault("summary", "")
    return parsed

def score_candidate(candidate_data: dict, job_description: str) -> dict:
    prompt = f"""You are a senior legal HR recruiter at a prestigious law firm.
Evaluate this candidate against the job description.
Return ONLY a valid JSON object with NO explanation, no markdown, no code fences.
Schema:
{{
  "score": 0,
  "tier": "top",
  "reasoning": "",
  "strengths": [],
  "concerns": [],
  "interview_questions": ["q1","q2","q3","q4","q5"]
}}
Rules:
- score: integer 0-100
- tier: 'top' if score >= 70, 'mid' if 50-69, 'reject' if below 50
- reasoning: 2-3 sentence explanation of the score
- strengths: list of 2-3 specific strengths from the resume
- concerns: list of 1-2 specific gaps or risks
- interview_questions: 5 highly specific questions tailored to THIS candidate's
  resume gaps and background - not generic questions
Job Description: {job_description[:2000]}
Candidate: Name={candidate_data.get('name')}, Experience={candidate_data.get('parsed_experience_years')}yrs, Role={candidate_data.get('parsed_current_role')}, Skills={candidate_data.get('parsed_skills')}, Education={candidate_data.get('parsed_education')}"""
    
    fallback = {
        "score": 0,
        "tier": "reject",
        "reasoning": "Scoring failed",
        "strengths": [],
        "concerns": [],
        "interview_questions": [
            "Please describe your relevant experience.",
            "What draws you to this role?",
            "Describe a challenging case you handled.",
            "How do you manage tight deadlines?",
            "Where do you see yourself in 5 years?"
        ]
    }
    
    try:
        response = model.generate_content(prompt)
        return _parse_json_response(response.text)
    except Exception as e:
        logger.error(f"Error scoring candidate: {e}")
        return fallback

def generate_rejection_body(name: str, job_title: str, strength: str) -> str:
    prompt = f"""Write a kind, professional rejection email body for a law firm applicant.
Name: {name}. Role: {job_title}. Acknowledge this specific strength: {strength}.
Encourage them to apply for future roles. Close warmly.
Max 100 words. Output ONLY the email body starting with 'Dear {name.split()[0] if name else 'Applicant'},'
No subject line, no signature, no markdown."""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating rejection body: {e}")
        return f"Dear {name.split()[0] if name else 'Applicant'},\n\nThank you for applying for the {job_title} position. While we were impressed by your background, particularly your {strength}, we have decided to move forward with other candidates at this time. We encourage you to apply for future roles that match your skills.\n\nWarm regards,"
