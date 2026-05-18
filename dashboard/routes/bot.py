"""
Bot management routes — activity log, cron config.
"""
import os
import json
import asyncio
import yaml
import requests
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from db import sql_query, sql_execute, INSTANCE

router = APIRouter()
templates = Jinja2Templates(directory="templates")
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/context.yaml")
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://host.docker.internal:12344")
LM_STUDIO_API_KEY = os.environ.get("LM_STUDIO_API_KEY", "")


@router.get("/bot/activity", response_class=HTMLResponse)
async def activity_page(request: Request, page: int = 0, classification: str = ""):
    limit = 50
    offset = page * limit
    filt = ""
    params = (limit, offset)
    if classification:
        filt = "WHERE classification = %s"
        params = (classification, limit, offset)
    try:
        logs = sql_query(f"""
            SELECT TOP 200 id, message_id, chat_jid, sender, content,
                   classification, action_taken, reply_text, processed_at
            FROM {INSTANCE}_message_log
            {filt}
            ORDER BY processed_at DESC
        """) if not classification else sql_query(f"""
            SELECT TOP 200 id, message_id, chat_jid, sender, content,
                   classification, action_taken, reply_text, processed_at
            FROM {INSTANCE}_message_log
            WHERE classification = %s
            ORDER BY processed_at DESC
        """, (classification,))
    except Exception:
        logs = []
    return templates.TemplateResponse(request, "activity.html", {
        "page": "activity",
        "logs": logs, "classification_filter": classification,
        "instance_name": INSTANCE,
    })


@router.get("/bot/config", response_class=HTMLResponse)
async def config_page(request: Request):
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}
    
    # Fetch available models from LM Studio for drop-down selection
    loaded_models = []
    headers = {}
    if LM_STUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LM_STUDIO_API_KEY}"
    try:
        resp = requests.get(f"{LM_STUDIO_URL}/v1/models", headers=headers, timeout=3)
        if resp.status_code == 200:
            loaded_models = [m["id"] for m in resp.json().get("data", [])]
    except Exception:
        pass

    return templates.TemplateResponse(request, "config.html", {
        "page": "config",
        "config": config,
        "loaded_models": loaded_models,
        "instance_name": INSTANCE,
    })


@router.post("/bot/config")
async def update_config(
    request: Request,
    check_interval_minutes: int = Form(3),
    cooldown_minutes: int = Form(10),
    max_replies_per_chat_per_day: int = Form(10),
    reply_to_groups: bool = Form(False),
    system_prompt: str = Form(""),
    llm_base_url: str = Form(""),
    llm_api_key: str = Form(""),
    llm_model: str = Form(""),
    llm_temperature: float = Form(0.7),
    llm_max_tokens: int = Form(300),
):
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        config["check_interval_minutes"] = check_interval_minutes
        config["cooldown_minutes"] = cooldown_minutes
        config["max_replies_per_chat_per_day"] = max_replies_per_chat_per_day
        config["reply_to_groups"] = reply_to_groups
        config["system_prompt"] = system_prompt
        
        # Update LLM settings
        if "llm" not in config:
            config["llm"] = {}
        config["llm"]["base_url"] = llm_base_url
        config["llm"]["api_key"] = llm_api_key
        config["llm"]["model"] = llm_model
        config["llm"]["temperature"] = llm_temperature
        config["llm"]["max_tokens"] = llm_max_tokens
        
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception:
        pass
    return RedirectResponse("/bot/config", status_code=303)


@router.get("/api/sse/activity")
async def sse_activity(request: Request):
    async def event_gen():
        last_id = 0
        while True:
            if await request.is_disconnected():
                break
            try:
                rows = sql_query(f"""
                    SELECT TOP 10 id, message_id, chat_jid, sender, content,
                           classification, action_taken, reply_text, processed_at
                    FROM {INSTANCE}_message_log
                    WHERE id > %s ORDER BY id DESC
                """, (last_id,))
                if rows:
                    last_id = max(r["id"] for r in rows)
                    yield {"event": "activity_update", "data": json.dumps(rows, default=str)}
            except Exception:
                pass
            await asyncio.sleep(5)
    return EventSourceResponse(event_gen())
