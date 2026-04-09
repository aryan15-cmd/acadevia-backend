import csv
import os

DATA = None  # ✅ cache once


def load_dataset():
    global DATA

    # ✅ Prevent reloading (IMPORTANT)
    if DATA is not None:
        return DATA

    DATA = []

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(BASE_DIR, "data", "dataset.csv")

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:

            subject = row.get("Subject", "").strip()
            topic = row.get("Chapter/Topics", "").strip()
            details = row.get("Details", "").strip()
            time = row.get("Estimated Time", "").strip()

            # ❌ skip empty rows
            if not (subject or topic or details):
                continue

            # 🔥 ULTRA COMPACT FORMAT (token optimized)
            compact = f"{subject}|{topic}|{details}|{time}".lower()

            DATA.append(compact)

    return DATA