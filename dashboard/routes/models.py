"""
LM Studio model management routes.
"""
import os
import requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import INSTANCE

router = APIRouter()
templates = Jinja2Templates(directory="templates")
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://192.168.1.32:1234")
LM_STUDIO_API_KEY = os.environ.get("LM_STUDIO_API_KEY", "")


@router.get("/models", response_class=HTMLResponse)
async def models_page(request: Request):
    models_data = []
    lm_status = "offline"
    headers = {}
    if LM_STUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LM_STUDIO_API_KEY}"
    try:
        resp = requests.get(f"{LM_STUDIO_URL}/v1/models", headers=headers, timeout=5)
        if resp.status_code == 200:
            lm_status = "online"
            data = resp.json()
            models_data = data.get("data", [])
    except Exception:
        lm_status = "offline"
    return templates.TemplateResponse(request, "models.html", {
        "page": "models",
        "models": models_data, "lm_status": lm_status,
        "lm_url": LM_STUDIO_URL, "instance_name": INSTANCE,
    })


@router.get("/api/models")
async def api_models():
    headers = {}
    if LM_STUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {LM_STUDIO_API_KEY}"
    try:
        resp = requests.get(f"{LM_STUDIO_URL}/v1/models", headers=headers, timeout=5)
        if resp.status_code == 200:
            return {"status": "online", "models": resp.json().get("data", [])}
    except Exception:
        pass
    return {"status": "offline", "models": []}
