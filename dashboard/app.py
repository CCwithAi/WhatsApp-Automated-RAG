"""
WhatsApp Bot Dashboard — FastAPI Entry Point
"""
import os
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from routes import chats, bot, marketing, models, training

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("dashboard")

app = FastAPI(title="WhatsApp Bot Dashboard")

# Static files + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include route modules
app.include_router(chats.router)
app.include_router(bot.router)
app.include_router(marketing.router)
app.include_router(models.router)
app.include_router(training.router)

# Shared config
INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "cleaner")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard home page."""
    return templates.TemplateResponse(request, "base.html", {
        "page": "home",
        "instance_name": INSTANCE_NAME,
    })
