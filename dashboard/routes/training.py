"""
Training pipeline routes + RAG.
"""
import os
import json
import asyncio
import threading
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from db import sql_query, sql_execute, INSTANCE
from training.pipeline import run_training_pipeline, training_status

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/training", response_class=HTMLResponse)
async def training_page(request: Request):
    stats = {"chunks": 0, "runs": [], "last_run": None}
    try:
        chunks = sql_query(f"SELECT COUNT(*) as cnt FROM {INSTANCE}_training_chunks")
        stats["chunks"] = chunks[0]["cnt"] if chunks else 0
        runs = sql_query(f"""
            SELECT TOP 10 id, started_at, completed_at, status,
                   messages_processed, chunks_created, embeddings_generated, error_message
            FROM {INSTANCE}_training_runs ORDER BY started_at DESC
        """)
        stats["runs"] = runs
        if runs:
            stats["last_run"] = runs[0]
    except Exception:
        pass
    return templates.TemplateResponse(request, "training.html", {
        "page": "training",
        "stats": stats, "status": training_status,
        "instance_name": INSTANCE,
    })


@router.post("/training/run")
async def trigger_training(request: Request):
    if training_status.get("running"):
        return {"status": "already_running"}
    thread = threading.Thread(target=run_training_pipeline, daemon=True)
    thread.start()
    return {"status": "started"}


@router.get("/api/sse/training")
async def sse_training(request: Request):
    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "training_status", "data": json.dumps(training_status, default=str)}
            if not training_status.get("running"):
                break
            await asyncio.sleep(2)
    return EventSourceResponse(event_gen())
