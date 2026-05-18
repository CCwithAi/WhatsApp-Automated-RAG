"""
Marketing queue routes.
"""
import os
import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import sql_query, sql_execute, INSTANCE

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/bot/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request):
    try:
        pending = sql_query(f"""
            SELECT id, content, target_groups, scheduled_at, status, created_at
            FROM {INSTANCE}_marketing_messages ORDER BY created_at DESC
        """)
    except Exception:
        pending = []
    return templates.TemplateResponse(request, "marketing.html", {
        "page": "marketing",
        "messages": pending, "instance_name": INSTANCE,
    })


@router.post("/bot/marketing")
async def create_marketing(request: Request, content: str = Form(""), scheduled_at: str = Form("")):
    sched = f"'{scheduled_at}'" if scheduled_at else "NULL"
    sql_execute(f"""
        INSERT INTO {INSTANCE}_marketing_messages (content, scheduled_at)
        VALUES (%s, {"NULL" if not scheduled_at else "%s"})
    """, (content,) if not scheduled_at else (content, scheduled_at))
    return RedirectResponse("/bot/marketing", status_code=303)


@router.post("/bot/marketing/{mid}/delete")
async def delete_marketing(mid: int):
    sql_execute(f"DELETE FROM {INSTANCE}_marketing_messages WHERE id = %s AND status = 'pending'", (mid,))
    return RedirectResponse("/bot/marketing", status_code=303)
