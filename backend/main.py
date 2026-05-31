from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uvicorn

from database import get_db
import models
import schemas

from api import auth as api_auth
from api import events as api_events
from api import availabilities as api_availabilities
from api import admin_settings as api_admin_settings

app = FastAPI(title="EventFinder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_auth.router, prefix="/auth", tags=["auth"])
app.include_router(api_events.router, prefix="/events", tags=["events"])
app.include_router(api_availabilities.router, prefix="/events", tags=["availabilities"])
app.include_router(api_admin_settings.router, prefix="/api/admin", tags=["admin"])

os.makedirs("/app/uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")

@app.get("/")
async def root():
    return {"message": "Welcome to EventFinder API"}

# Hier werden die Router später eingebunden
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(events.router, prefix="/events", tags=["events"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
