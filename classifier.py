"""Use Claude to decide if an email is about one of YOUR job applications
and to extract structured fields."""
import json
import os

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

SYSTEM = """You extract job-application information from a single email.

Return ONLY a JSON object with these keys:
- relevant: true only if the email is about a specific job the recipient applied
  for or is being considered for (confirmation, assessment, interview invite,
  offer, rejection, recruiter outreach about a named role). False for
  newsletters, job-alert digests, ads, and unrelated mail.
- company: employer name (not the ATS vendor like Greenhouse/Workday/Lever)
- role: job title, or "" if unknown
- status: one of "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"
    Applied    = application received/confirmed, or recruiter outreach
    Assessment = coding test, take-home, or screening questionnaire requested
    Interview  = interview scheduled or requested (phone, onsite, panel)
    Offer      = offer extended
    Rejected   = not moving forward
    Withdrawn  = candidate withdrew
- contact: recruiter/sender name and email if present, else ""
- job_link: URL of the posting if present, else ""
- notes: one short sentence with key details (e.g. interview date/time, deadline)

If relevant is false, the other fields may be empty strings."""


def classify(email: dict) -> dict:
    client = anthropic.Anthropic()
    content = (
        f"From: {email['from']}\nSubject: {email['subject']}\n"
        f"Date: {email['date']}\n\n{email['body']}"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    try:
        return json.loads(text[text.find("{"): text.rfind("}") + 1])
    except Exception:
        return {"relevant": False}
