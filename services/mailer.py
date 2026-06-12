import smtplib
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from config import settings
import os

logger = logging.getLogger(__name__)

# Setup Jinja2 environment for emails
template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "emails")
env = Environment(loader=FileSystemLoader(template_dir))

def _render_email_template(template_name: str, context: dict) -> str:
    template = env.get_template(template_name)
    # inject firm name globally
    context["FIRM_NAME"] = settings.FIRM_NAME
    return template.render(context)

def send_html_email(to: str, subject: str, html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.FIRM_NAME} <{settings.GMAIL_SENDER_EMAIL}>"
        msg["To"] = to

        # Create plain text version by stripping tags
        text = re.sub(r'<[^>]+>', '', html)
        
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_SENDER_EMAIL, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_SENDER_EMAIL, to, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False

def send_acknowledgment(name: str, email: str, job_title: str) -> bool:
    subject = f"Application Received — {job_title} | {settings.FIRM_NAME}"
    html = _render_email_template("acknowledgment.html", {"name": name, "job_title": job_title})
    return send_html_email(email, subject, html)

def send_interview_invite(name: str, email: str, job_title: str, calendly_link: str) -> bool:
    subject = f"Interview Invitation — {job_title} | {settings.FIRM_NAME}"
    html = _render_email_template("interview_invite.html", {
        "name": name, 
        "job_title": job_title, 
        "calendly_link": calendly_link
    })
    return send_html_email(email, subject, html)

def send_rejection(name: str, email: str, job_title: str, rejection_body: str) -> bool:
    subject = f"Your Application — {job_title} | {settings.FIRM_NAME}"
    html = _render_email_template("rejection.html", {
        "name": name, 
        "job_title": job_title, 
        "rejection_body": rejection_body
    })
    return send_html_email(email, subject, html)

def send_interviewer_brief(hr_email: str, candidate_name: str, job_title: str, score: float, strengths: list, concerns: list, questions: list) -> bool:
    subject = f"[Interview Brief] {candidate_name} — {job_title}"
    score_color = "green" if score and score >= 70 else "orange"
    
    strengths_html = "".join([f"<li>{s}</li>" for s in strengths])
    concerns_html = "".join([f"<li>{c}</li>" for c in concerns])
    questions_html = "".join([f"<li>{q}</li>" for q in questions])
    
    html = f"""
    <html>
        <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>Interview Brief: {candidate_name}</h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Role</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{job_title}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>AI Score</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd; color: {score_color}; font-weight: bold;">{score} / 100</td>
                </tr>
            </table>
            
            <h3>Strengths</h3>
            <ul>{strengths_html}</ul>
            
            <h3>Concerns</h3>
            <ul>{concerns_html}</ul>
            
            <h3>Suggested Interview Questions</h3>
            <ol>{questions_html}</ol>
        </body>
    </html>
    """
    return send_html_email(hr_email, subject, html)
