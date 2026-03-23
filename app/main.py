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
def send_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)
@app.get("/miniapp", response_class=HTMLResponse)
def miniapp(tg_user_id: Optional[int] = None, full_name: Optional[str] = None):
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Taom Team</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{
                --bg: #f3f4f6;
                --card: #ffffff;
                --text: #1f2937;
                --muted: #6b7280;
                --primary: #0f172a;
                --green: #57a769;
                --border: #e5e7eb;
                --shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
            }}
            * {{
                box-sizing: border-box;
                -webkit-tap-highlight-color: transparent;
            }}
            body {{
                margin: 0;
                background: var(--bg);
                color: var(--text);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            .app {{
                max-width: 520px;
                margin: 0 auto;
                padding: 16px;
            }}
            .hero {{
                background: linear-gradient(135deg, #111827 0%, #172554 100%);
                color: #fff;
                border-radius: 28px;
                padding: 20px;
                box-shadow: var(--shadow);
                margin-bottom: 16px;
            }}
            .hero-top {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
            }}
            .brand {{
                font-size: 14px;
                opacity: 0.9;
                margin-bottom: 8px;
            }}
            .title {{
                margin: 0;
                font-size: 30px;
                font-weight: 800;
                line-height: 1.05;
            }}
            .subtitle {{
                margin: 10px 0 0;
                font-size: 15px;
                line-height: 1.45;
                color: rgba(255,255,255,0.85);
            }}
            .status {{
                min-width: 120px;
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 20px;
                padding: 14px;
                text-align: center;
            }}
            .status small {{
                display: block;
                font-size: 13px;
                opacity: 0.85;
                margin-bottom: 6px;
            }}
            .status strong {{
                font-size: 20px;
            }}
            .user-box {{
                margin-top: 18px;
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 22px;
                padding: 16px;
            }}
            .user-box .label {{
                font-size: 13px;
                color: rgba(255,255,255,0.75);
                margin-bottom: 8px;
            }}
            .user-box .name {{
                font-size: 22px;
                font-weight: 800;
                margin-bottom: 6px;
            }}
            .user-box .id {{
                font-size: 14px;
                color: rgba(255,255,255,0.78);
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 14px;
                margin-bottom: 22px;
            }}
            .stat {{
                background: var(--card);
                border-radius: 24px;
                padding: 18px;
                border: 1px solid var(--border);
                box-shadow: var(--shadow);
            }}
            .stat-label {{
                font-size: 14px;
                color: var(--muted);
                margin-bottom: 12px;
            }}
            .stat-value {{
                font-size: 30px;
                font-weight: 800;
                line-height: 1;
                margin-bottom: 12px;
            }}
            .stat-note {{
                font-size: 13px;
                color: var(--green);
                font-weight: 700;
            }}
            .section-title {{
                font-size: 22px;
                font-weight: 800;
                margin: 8px 0 14px;
            }}
            .action-card {{
                background: var(--card);
                border-radius: 24px;
                border: 1px solid var(--border);
                box-shadow: var(--shadow);
                padding: 18px;
                margin-bottom: 16px;
            }}
            .action-head {{
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 12px;
            }}
            .action-name {{
                font-size: 24px;
                font-weight: 800;
                margin: 0 0 10px;
            }}
            .action-desc {{
                margin: 0;
                color: var(--muted);
                font-size: 15px;
                line-height: 1.45;
            }}
            .icon-box {{
                width: 64px;
                height: 64px;
                border-radius: 18px;
                background: #f3f4f6;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 30px;
            }}
            .btn-row {{
                display: flex;
                gap: 14px;
                margin-top: 18px;
                flex-wrap: wrap;
            }}
            button {{
                border: none;
                border-radius: 18px;
                padding: 16px 28px;
                font-size: 18px;
                font-weight: 800;
                cursor: pointer;
            }}
            .btn-primary {{
                background: #0f172a;
                color: white;
            }}
            .btn-secondary {{
                background: #eef0f3;
                color: #1f2937;
            }}
            .mini-item {{
                background: var(--card);
                border-radius: 22px;
                border: 1px solid var(--border);
                box-shadow: var(--shadow);
                padding: 18px;
                margin-bottom: 12px;
            }}
            .mini-item-title {{
                font-size: 20px;
                font-weight: 800;
                margin-bottom: 8px;
            }}
            .mini-item-sub {{
                color: var(--muted);
                font-size: 15px;
                line-height: 1.4;
            }}
            .report-form {{
                display: none;
                background: var(--card);
                border-radius: 24px;
                border: 1px solid var(--border);
                box-shadow: var(--shadow);
                padding: 18px;
                margin-top: 18px;
            }}
            .report-form.show {{
                display: block;
            }}
            .report-form h3 {{
                margin: 0 0 14px;
                font-size: 24px;
            }}
            .report-form label {{
                display: block;
                font-size: 14px;
                margin-bottom: 6px;
                color: var(--muted);
            }}
            .report-form input,
            .report-form textarea {{
                width: 100%;
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 14px;
                font-size: 16px;
                margin-bottom: 12px;
                background: #fff;
            }}
            .report-form textarea {{
                min-height: 110px;
                resize: vertical;
            }}
        </style>
    </head>
    <body>
        <div class="app">
            <div class="hero">
                <div class="hero-top">
                    <div>
                        <div class="brand">Taom Team • Dashboard</div>
                        <h1 class="title">Главный экран</h1>
                        <p class="subtitle">Отчёты, аналитика, официанты и KPI в одном месте.</p>
                    </div>
                    <div class="status">
                        <small>Статус</small>
                        <strong>Online</strong>
                    </div>
                </div>

                <div class="user-box">
                    <div class="label">Пользователь</div>
                    <div class="name">{full_name or ""}</div>
                    <div class="id">ID: {tg_user_id or ""}</div>
                </div>
            </div>

            <div class="grid">
                <div class="stat">
                    <div class="stat-label">Выручка сегодня</div>
                    <div class="stat-value">0 сум</div>
                    <div class="stat-note">Готово к подключению</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Средний чек</div>
                    <div class="stat-value">0 сум</div>
                    <div class="stat-note">Готово к подключению</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Гостей</div>
                    <div class="stat-value">0</div>
                    <div class="stat-note">Готово к подключению</div>
                </div>
                <div class="stat">
                    <div class="stat-label">KPI</div>
                    <div class="stat-value">0%</div>
                    <div class="stat-note">Готово к подключению</div>
                </div>
            </div>

            <div class="section-title">Быстрые действия</div>

            <div class="action-card">
                <div class="action-head">
                    <div>
                        <div class="action-name">Отчёт смены</div>
                        <p class="action-desc">Заполнение и отправка ежедневного отчёта менеджера.</p>
                    </div>
                    <div class="icon-box">📝</div>
                </div>
                <div class="btn-row">
                    <button class="btn-primary" onclick="openReport()">Открыть</button>
                    <button class="btn-secondary" onclick="openHistory()">История</button>
                </div>
            </div>

            <div class="action-card">
                <div class="action-head">
                    <div>
                        <div class="action-name">Сводка дня</div>
                        <p class="action-desc">Короткая аналитика по выручке, гостям, среднему чеку и персоналу.</p>
                    </div>
                    <div class="icon-box">📊</div>
                </div>
                <div class="btn-row">
                    <button class="btn-primary" onclick="openSummary()">Смотреть</button>
                    <button class="btn-secondary" onclick="exportSummary()">Экспорт</button>
                </div>
            </div>

            <div class="section-title">Блоки</div>

            <div class="mini-item">
                <div class="mini-item-title">Официанты</div>
                <div class="mini-item-sub">Показатели по персоналу, продажи и эффективность.</div>
            </div>

            <div class="mini-item">
                <div class="mini-item-title">KPI менеджера</div>
                <div class="mini-item-sub">Оценка открытия, чистоты, дисциплины и срочных инцидентов.</div>
            </div>

            <div class="mini-item">
                <div class="mini-item-title">iiko Sync</div>
                <div class="mini-item-sub">Подключение и синхронизация данных из iiko.</div>
            </div>

            <div id="reportForm" class="report-form">
                <h3>Отчёт смены</h3>

                <label for="guests">Гостей</label>
                <input id="guests" type="number" placeholder="Например: 120">

                <label for="avg">Средний чек (сум)</label>
                <input id="avg" type="number" placeholder="Например: 85000">

                <label for="comment">Комментарий</label>
                <textarea id="comment" placeholder="Что было за смену..."></textarea>

                <div class="btn-row">
                    <button class="btn-primary" onclick="sendReport()">Отправить отчёт</button>
                    <button class="btn-secondary" onclick="closeReport()">Закрыть</button>
                </div>
            </div>
        </div>

        <script>
            const tg = window.Telegram.WebApp;
            tg.expand();

            function openReport() {{
                document.getElementById('reportForm').classList.add('show');
                window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
            }}

            function closeReport() {{
                document.getElementById('reportForm').classList.remove('show');
            }}

            function openHistory() {{
                alert('История отчётов пока в разработке');
            }}

            function openSummary() {{
                alert('Сводка дня пока в разработке');
            }}

            function exportSummary() {{
                alert('Экспорт пока в разработке');
            }}

            async function sendReport() {
    const guests = document.getElementById('guests').value;
    const avg = document.getElementById('avg').value;
    const comment = document.getElementById('comment').value;

    if (!guests || !avg) {
        alert("Заполни гостей и средний чек");
        return;
    }

    try {
        const response = await fetch("/api/report", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                telegram_user_id: {{ tg_user_id }},
                manager_name: "{{ full_name }}",
                guests_count: Number(guests),
                avg_check: Number(avg),
                comment_text: comment
            })
        });

        if (response.ok) {
            alert("Отчёт сохранён ✅");
        } else {
            alert("Ошибка сервера ❌");
        }

    } catch (e) {
        alert("Ошибка соединения ❌");
    }
}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
    return templates.TemplateResponse("miniapp.html", context) 
