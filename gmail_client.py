"""Read-only Gmail access via the Gmail API."""
import base64
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Broad pre-filter so we only send plausible job emails to Claude.
JOB_QUERY = (
    '(application OR applied OR "your candidacy" OR interview OR "next steps" '
    'OR recruiter OR "job opportunity" OR offer OR "unfortunately" OR "position" '
    'OR assessment OR "thank you for applying") '
    '-category:promotions -category:social'
)


def get_service(credentials_file="credentials.json", token_file="token.json"):
    creds = None
    if Path(token_file).exists():
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(token_file).write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def list_message_ids(service, after_date: str, max_results=200):
    """after_date: YYYY/MM/DD"""
    q = f"{JOB_QUERY} after:{after_date}"
    ids, token = [], None
    while len(ids) < max_results:
        resp = service.users().messages().list(
            userId="me", q=q, pageToken=token, maxResults=100).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        token = resp.get("nextPageToken")
        if not token:
            break
    return ids[:max_results]


def _walk_parts(payload):
    if payload.get("parts"):
        for p in payload["parts"]:
            yield from _walk_parts(p)
    else:
        yield payload


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def get_message(service, msg_id: str) -> dict:
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    plain, html = "", ""
    for part in _walk_parts(msg["payload"]):
        data = part.get("body", {}).get("data")
        if not data:
            continue
        if part.get("mimeType") == "text/plain":
            plain += _decode(data)
        elif part.get("mimeType") == "text/html":
            html += _decode(data)
    body = plain or _html_to_text(html)
    try:
        date = parsedate_to_datetime(headers.get("date", "")).date().isoformat()
    except Exception:
        date = ""
    return {
        "id": msg_id,
        "from": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "date": date,
        "body": body[:6000],
    }
