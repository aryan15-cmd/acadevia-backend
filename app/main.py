from fastapi import FastAPI, Depends
from .db.database import Base, engine
from app.api import auth, tasks, focus, blocker
from app.api.auth import get_current_user
from fastapi.middleware.cors import CORSMiddleware
from app.api import analytics
from app.api import stats
from app.api.ai import router as ai_router
from app.api.daily_report import router as daily_router
from app.api.ai_planner import router as ai_plan_router
# Create FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change later for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
app.include_router(focus.router, prefix="/focus", tags=["Focus"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(stats.router, prefix="/stats", tags=["Stats"])
app.include_router(blocker.router)
app.include_router(ai_router)
app.include_router(daily_router)
app.include_router(ai_plan_router)
@app.get("/")
def root():
    return {"message": "FocusFlow Backend Running"}


@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return {
        "email": user.email,
        "name": user.full_name
    }