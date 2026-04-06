from fastapi import APIRouter
import json
import os

router = APIRouter()

ATTEMPT_FILE = "block_attempts.json"

@router.get("/block-attempts")
def get_attempts():

    if not os.path.exists(ATTEMPT_FILE):
        return {"attempts": 0}

    with open(ATTEMPT_FILE, "r") as f:
        data = json.load(f)

    return data