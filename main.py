"""Job application tracker.

Usage:
  python main.py init                 # create job_tracker.xlsx
  python main.py sync                 # scan Gmail once and update the sheet
  python main.py sync --days 90       # first run: look back 90 days
  python main.py watch --every 60     # keep running, sync every 60 minutes
"""
import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

import excel_store
from classifier import classify
from gmail_client import get_message, get_service, list_message_ids

load_dotenv()

EXCEL_PATH = "job_tracker.xlsx"
STATE_PATH = Path("state.json")


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"processed": [], "last_sync": None}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def sync(days: int | None) -> None:
    excel_store.init_workbook(EXCEL_PATH)
    state = load_state()
    processed = set(state["processed"])

    if days is None:
        days = 14 if state["last_sync"] is None else 3  # small overlap is safe
    after = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")

    service = get_service()
    ids = [i for i in list_message_ids(service, after) if i not in processed]
    print(f"Found {len(ids)} new candidate emails (since {after}).")

    counts = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    for msg_id in sorted(ids):
        email = get_message(service, msg_id)
        info = classify(email)
        processed.add(msg_id)
        if not info.get("relevant") or not info.get("company"):
            counts["skipped"] += 1
            continue
        result = excel_store.upsert(
            EXCEL_PATH, info, msg_id, email["date"] or excel_store.today())
        counts[result] += 1
        print(f"  [{result}] {info['company']} - {info.get('role') or '?'} "
              f"-> {info['status']}")

    state["processed"] = sorted(processed)
    state["last_sync"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    print("Done:", counts)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    s = sub.add_parser("sync")
    s.add_argument("--days", type=int, default=None)
    w = sub.add_parser("watch")
    w.add_argument("--every", type=int, default=60, help="minutes between syncs")
    w.add_argument("--days", type=int, default=None)
    args = ap.parse_args()

    if args.cmd == "init":
        excel_store.init_workbook(EXCEL_PATH)
        print(f"Created {EXCEL_PATH}")
    elif args.cmd == "sync":
        sync(args.days)
    elif args.cmd == "watch":
        while True:
            try:
                sync(args.days)
            except Exception as e:  # keep the loop alive on transient errors
                print("Sync failed:", e)
            args.days = None
            time.sleep(args.every * 60)


if __name__ == "__main__":
    main()
