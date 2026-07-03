"""
CSV storage helper: appends one row per processed email.
Columns: timestamp, sender_email, subject, message, gemini_output
"""
import csv
import os
from datetime import datetime, timezone

import config

FIELDNAMES = ["timestamp", "sender_email", "subject", "message", "gemini_output"]


def append_result(sender_email: str, subject: str, message: str, gemini_output: str):
    file_exists = os.path.exists(config.OUTPUT_CSV)
    with open(config.OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender_email": sender_email,
            "subject": subject,
            "message": message,
            "gemini_output": gemini_output,
        })
