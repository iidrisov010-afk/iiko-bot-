import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import execute, query_all, query_one
from .models import ManagerReportIn, SyncPayload
from .services import IikoService, KPIService

BASE_DIR = Path(__file__).resolve().parent.parent

BOT_TOKEN = "ТВОЙ_ТОКЕН"
BOT_USERNAME = "TAOM_TEAMUZBOT"
APP_BASE_URL = "https://iiko-bot.onrender.com"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

app = FastAPI(title="iiko Telegram Mini App v2")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "app" / "static")),
    name="static"
)

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

iiko_service = IikoService()
kpi_service = KPIService()
@app.get("/miniapp", response_class=HTMLResponse)
def miniapp(request: Request, tg_user_id: Optional[int] = None, full_name: Optional[str] = None):
    return templates.TemplateResponse(
        "miniapp.html",
        {
            "request": request,
            "tg_user_id": tg_user_id or "",
            "full_name": full_name or "",
        },
    )
def send_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)    
