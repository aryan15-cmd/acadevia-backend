import psutil
import sys
import time
import json
import os

blocked_apps = sys.argv[1:]

ATTEMPT_FILE = "block_attempts.json"

def update_attempts():
    if not os.path.exists(ATTEMPT_FILE):
        data = {"attempts": 0}
    else:
        with open(ATTEMPT_FILE, "r") as f:
            data = json.load(f)

    data["attempts"] += 1

    with open(ATTEMPT_FILE, "w") as f:
        json.dump(data, f)


while True:

    for proc in psutil.process_iter(["name"]):

        try:

            if proc.info["name"] in blocked_apps:

                proc.kill()
                update_attempts()

        except:
            pass

    time.sleep(2)