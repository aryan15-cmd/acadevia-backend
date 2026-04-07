import csv
import os

DATA = []

def load_dataset():
    global DATA

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(BASE_DIR, "data", "dataset.csv")

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            # 🔥 UPDATED LINE (TOKEN OPTIMIZED)
            compact = f"{row.get('Subject','')} | {row.get('Chapter/Topics','')} | {row.get('Details','')} | {row.get('Estimated Time','')}".strip().lower()

            DATA.append(compact)

    return DATA