"""Excel tracker: create the workbook, add applications, update statuses."""
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

COLUMNS = [
    "Company", "Role", "Status", "Date Applied", "Last Update",
    "Contact", "Job Link", "Notes", "Email ID",
]
WIDTHS = [24, 30, 16, 14, 14, 26, 36, 60, 20]

# Higher rank = further along. A status never moves backwards automatically,
# except Rejected / Withdrawn which are terminal and always win.
STATUSES = ["Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]
RANK = {"Applied": 1, "Assessment": 2, "Interview": 3, "Offer": 4,
        "Rejected": 99, "Withdrawn": 99}

STATUS_COLORS = {
    "Applied": "DDEBF7", "Assessment": "FFF2CC", "Interview": "FCE4D6",
    "Offer": "C6EFCE", "Rejected": "F8CBAD", "Withdrawn": "EDEDED",
}


def init_workbook(path: str) -> None:
    p = Path(path)
    if p.exists():
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(COLUMNS)
    for i, w in enumerate(WIDTHS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
        c.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(COLUMNS)).column_letter}1"
    wb.save(p)


def _norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def _find_row(ws, company: str, role: str):
    """Match on company (+ role when both sides have one)."""
    best = None
    for r in range(2, ws.max_row + 1):
        if _norm(ws.cell(r, 1).value) != _norm(company):
            continue
        existing_role = _norm(ws.cell(r, 2).value)
        if role and existing_role and existing_role == _norm(role):
            return r  # exact company + role match
        if not role or not existing_role:
            best = best or r  # company-only match as a fallback
    return best


def _color_status(ws, row: int) -> None:
    status = ws.cell(row, 3).value
    color = STATUS_COLORS.get(status)
    if color:
        ws.cell(row, 3).fill = PatternFill("solid", fgColor=color)


def upsert(path: str, info: dict, email_id: str, email_date: str) -> str:
    """Insert or update a row. Returns 'added', 'updated' or 'unchanged'."""
    init_workbook(path)
    wb = load_workbook(path)
    ws = wb["Applications"]

    company = (info.get("company") or "").strip()
    role = (info.get("role") or "").strip()
    status = info.get("status") if info.get("status") in RANK else "Applied"
    notes = (info.get("notes") or "").strip()
    contact = (info.get("contact") or "").strip()
    link = (info.get("job_link") or "").strip()

    row = _find_row(ws, company, role)
    if row is None:
        first_note = f"[{email_date}] {notes}" if notes else ""
        ws.append([company, role, status, email_date, email_date,
                   contact, link, first_note, email_id])
        _color_status(ws, ws.max_row)
        wb.save(path)
        return "added"

    changed = False
    current = ws.cell(row, 3).value or "Applied"
    if RANK.get(status, 0) > RANK.get(current, 0) and current not in ("Rejected", "Withdrawn"):
        ws.cell(row, 3).value = status
        _color_status(ws, row)
        changed = True
    if role and not ws.cell(row, 2).value:
        ws.cell(row, 2).value = role
        changed = True
    if contact and not ws.cell(row, 6).value:
        ws.cell(row, 6).value = contact
        changed = True
    if link and not ws.cell(row, 7).value:
        ws.cell(row, 7).value = link
        changed = True
    if notes:
        old = ws.cell(row, 8).value or ""
        line = f"[{email_date}] {notes}"
        if line not in old:
            ws.cell(row, 8).value = (old + "\n" + line).strip()
            changed = True
    if changed:
        ws.cell(row, 5).value = email_date
        ws.cell(row, 9).value = email_id
        wb.save(path)
        return "updated"
    return "unchanged"


def today() -> str:
    return date.today().isoformat()
