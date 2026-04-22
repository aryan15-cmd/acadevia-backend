import csv
import os

DATA = None

def load_dataset():
    global DATA

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
            semester = row.get("Semester", "").strip()

            #  skip empty rows
            if not (subject or topic):
                continue

            DATA.append({
                "subject": subject.lower(),
                "topic": topic,
                "details": details,
                "time": int(time) if time.isdigit() else 2,
                "semester": semester
            })

    return DATA