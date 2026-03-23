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
BOT_TOKEN = "8319602648:AAHEuAd2etwwJMVuz2JlQgBHYe27DOebAy4"
BOT_USERNAME = "TAOM_TEAMUZBOT"
APP_BASE_URL ="https://iiko-bot.onrender.com"
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}' if BOT_TOKEN else ''

app = FastAPI(title='iiko Telegram Mini App v2')
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'app' / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'app' / 'templates'))
iiko_service = None
kpi_service = None


def init_db() -> None:
    execute(
        '''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER,
            manager_name TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            report_date TEXT NOT NULL,
            shift_name TEXT NOT NULL,
            guests_count INTEGER NOT NULL,
            avg_check REAL DEFAULT 0,
            complaints_count INTEGER DEFAULT 0,
            compliments_count INTEGER DEFAULT 0,
            stop_list TEXT DEFAULT '',
            issues_text TEXT DEFAULT '',
            comment_text TEXT DEFAULT '',
            opening_score INTEGER DEFAULT 0,
            cleanliness_score INTEGER DEFAULT 0,
            discipline_violations INTEGER DEFAULT 0,
            urgent_incidents INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        '''
    )
    execute(
        '''
        CREATE TABLE IF NOT EXISTS iiko_sales_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT NOT NULL,
            business_date TEXT NOT NULL,
            revenue REAL NOT NULL,
            checks_count INTEGER NOT NULL,
            guests_count INTEGER NOT NULL,
            avg_check REAL NOT NULL,
            discounts_amount REAL DEFAULT 0,
            deletes_count INTEGER DEFAULT 0,
            returns_count INTEGER DEFAULT 0,
            source TEXT NOT NULL,
            synced_at TEXT NOT NULL
        )
        '''
    )
    execute(
        '''
        CREATE TABLE IF NOT EXISTS waiter_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT NOT NULL,
            business_date TEXT NOT NULL,
            waiter_name TEXT NOT NULL,
            revenue REAL NOT NULL,
            checks_count INTEGER NOT NULL,
            guests_count INTEGER NOT NULL,
            avg_check REAL NOT NULL,
            upsell_rate REAL DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            guest_score REAL DEFAULT 0,
            source_metric_id INTEGER
        )
        '''
    )
    execute(
        '''
        CREATE TABLE IF NOT EXISTS kpi_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_date TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            total_score REAL NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        '''
    )


def send_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    if not TELEGRAM_API:
        return
    payload = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    requests.post(f'{TELEGRAM_API}/sendMessage', json=payload, timeout=15)


@app.on_event('startup')
def startup_event() -> None:
    pass


@app.get("/")
def home():
    return {"status": "ok", "bot": "running"}


@app.get('/miniapp', response_class=HTMLResponse)
def miniapp(tg_user_id: Optional[int] = None, full_name: Optional[str] = None):
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Taom</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {{
                --bg: #f5f7fb;
                --card: #ffffff;
                --text: #1f2937;
                --muted: #6b7280;
                --primary: #111827;
                --accent: #16a34a;
                --border: #e5e7eb;
                --shadow: 0 10px 30px rgba(17, 24, 39, 0.08);
                --radius: 20px;
            }}

            * {{
                box-sizing: border-box;
                -webkit-tap-highlight-color: transparent;
            }}

            body {{
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: var(--bg);
                color: var(--text);
            }}

            .app {{
                max-width: 520px;
                margin: 0 auto;
                min-height: 100vh;
                padding: 20px 16px 28px;
            }}

            .hero {{
                background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
                color: white;
                border-radius: 24px;
                padding: 22px 18px;
                box-shadow: var(--shadow);
                margin-bottom: 16px;
            }}

            .hero-top {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 12px;
            }}

            .brand {{
                font-size: 13px;
                opacity: 0.85;
                margin-bottom: 8px;
            }}

            .title {{
                font-size: 26px;
                font-weight: 800;
                line-height: 1.1;
                margin: 0 0 8px;
            }}

            .subtitle {{
                margin: 0;
                font-size: 14px;
                color: rgba(255,255,255,0.8);
                line-height: 1.45;
            }}

            .badge {{
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(255,255,255,0.18);
                padding: 10px 12px;
                border-radius: 14px;
                text-align: right;
                min-width: 110px;
            }}

            .badge-label {{
                font-size: 12px;
                opacity: 0.8;
            }}

            .badge-value {{
                margin-top: 4px;
                font-size: 18px;
                font-weight: 700;
            }}

            .user-card {{
                margin-top: 16px;
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 16px;
                padding: 12px 14px;
            }}

            .user-label {{
                font-size: 12px;
                color: rgba(255,255,255,0.72);
                margin-bottom: 4px;
            }}

            .user-name {{
                font-size: 16px;
                font-weight: 700;
            }}

            .grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                margin-bottom: 18px;
            }}

            .stat {{
                background: var(--card);
                border-radius: 18px;
                padding: 16px;
                box-shadow: var(--shadow);
                border: 1px solid var(--border);
            }}

            .stat-label {{
                font-size: 13px;
                color: var(--muted);
                margin-bottom: 10px;
            }}

            .stat-value {{
                font-size: 24px;
                font-weight: 800;
                line-height: 1;
margin-bottom: 8px;
            }}

            .stat-note {{
                font-size: 12px;
                color: #16a34a;
                font-weight: 600;
            }}

            .section {{
                margin-top: 18px;
            }}

            .section-title {{
                font-size: 18px;
                font-weight: 800;
                margin: 0 0 12px;
            }}

            .actions {{
                display: grid;
                gap: 12px;
            }}

            .action-card {{
                background: var(--card);
                border-radius: 20px;
                padding: 16px;
                box-shadow: var(--shadow);
                border: 1px solid var(--border);
            }}

            .action-top {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 10px;
            }}

            .action-name {{
                font-size: 17px;
                font-weight: 800;
                margin: 0;
            }}

            .action-icon {{
                width: 42px;
                height: 42px;
                border-radius: 14px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #f3f4f6;
                font-size: 20px;
            }}

            .action-desc {{
                margin: 0 0 14px;
                color: var(--muted);
                font-size: 14px;
                line-height: 1.45;
            }}

            .btn-row {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }}

            .btn {{
                border: none;
                border-radius: 14px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
            }}

            .btn-primary {{
                background: var(--primary);
                color: white;
            }}

            .btn-secondary {{
                background: #f3f4f6;
                color: var(--text);
            }}

            .mini-list {{
                display: grid;
                gap: 10px;
            }}

            .mini-item {{
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 14px;
                box-shadow: var(--shadow);
            }}

            .mini-item-title {{
                font-size: 15px;
                font-weight: 700;
                margin-bottom: 6px;
            }}

            .mini-item-sub {{
                font-size: 13px;
                color: var(--muted);
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
                    <div class="badge">
                        <div class="badge-label">Статус</div>
                        <div class="badge-value">Online</div>
                    </div>
                </div>

                <div class="user-card">
                    <div class="user-label">Пользователь</div>
                    <div class="user-name">{full_name or 'Manager'}</div>
                    <div class="user-label" style="margin-top:6px;">ID: {tg_user_id}</div>
                </div>
            </div>

            <div class="grid">
                <div class="stat">
                    <div class="stat-label">Выручка сегодня</div>
                    <div class="stat-value">0 ₸</div>
                    <div class="stat-note">Готово к подключению</div>
                </div>
                <div class="stat">
  <div class="stat-label">Средний чек</div>
                    <div class="stat-value">0 ₸</div>
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

            <div class="section">
                <h2 class="section-title">Быстрые действия</h2>
                <div class="actions">
                    <div class="action-card">
                        <div class="action-top">
                            <h3 class="action-name">Отчёт смены</h3>
                            <div class="action-icon">📝</div>
                        </div>
                        <p class="action-desc">Заполнение и отправка ежедневного отчёта менеджера.</p>
                        <div class="btn-row">
                            <button class="btn btn-primary">Открыть</button>
                            <button class="btn btn-secondary">История</button>
                        </div>
                    </div>

                    <div class="action-card">
                        <div class="action-top">
                            <h3 class="action-name">Сводка дня</h3>
                            <div class="action-icon">📊</div>
                        </div>
                        <p class="action-desc">Короткая аналитика по выручке, гостям, среднему чеку и персоналу.</p>
                        <div class="btn-row">
                            <button class="btn btn-primary">Смотреть</button>
                            <button class="btn btn-secondary">Экспорт</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">Блоки</h2>
                <div class="mini-list">
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
                </div>
            </div>
        </div>

        <script>
            const tg = window.Telegram.WebApp;
            tg.expand();
        </script>
    </body>
    </html>
    """              

@app.post('/api/report')
def create_report(payload: ManagerReportIn):
    report_id = execute(
        '''
        INSERT INTO daily_reports (
            telegram_user_id, manager_name, branch_name, report_date, shift_name,
            guests_count, avg_check, complaints_count, compliments_count,
            stop_list, issues_text, comment_text, opening_score, cleanliness_score,
            discipline_violations, urgent_incidents, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            payload.telegram_user_id,
            payload.manager_name,
            payload.branch_name,
            payload.report_date.isoformat(),
            payload.shift_name,
            payload.guests_count,
            payload.avg_check,
            payload.complaints_count,
            payload.compliments_count,
            payload.stop_list,
            payload.issues_text,
            payload.comment_text,
            payload.opening_score,
            payload.cleanliness_score,
            payload.discipline_violations,
            payload.urgent_incidents,
            datetime.utcnow().isoformat(),
        ),
    )
    return {'ok': True, 'report_id': report_id}


@app.post('/api/iiko/sync')
def sync_iiko(payload: SyncPayload):
    result = iiko_service.sync_daily_stub(payload.branch_name, payload.business_date.isoformat())
    return {'ok': True, 'sync': result, 'configured_real_iiko': iiko_service.is_configured()}


@app.post('/api/kpi/rebuild')
def rebuild_kpi(payload: SyncPayload):
    result = kpi_service.rebuild_daily_kpi(payload.branch_name, payload.business_date.isoformat())
    return {'ok': True, 'result': result}


@app.get('/api/dashboard')
def dashboard(branch_name: Optional[str] = None, business_date: Optional[str] = None):
    filters = []
    params: list[object] = []
    if branch_name:
        filters.append('branch_name = ?')
        params.append(branch_name)
    if business_date:
        filters.append('business_date = ?')
        params.append(business_date)
    where = f"WHERE {' AND '.join(filters)}" if filters else ''

    sales = query_all(f'SELECT * FROM iiko_sales_daily {where} ORDER BY synced_at DESC LIMIT 10', params)
    reports = query_all(
        'SELECT * FROM daily_reports ORDER BY created_at DESC LIMIT 10'
        if not branch_name
        else 'SELECT * FROM daily_reports WHERE branch_name = ? ORDER BY created_at DESC LIMIT 10',
        [] if not branch_name else [branch_name],
    )
    kpi = query_all(
        'SELECT * FROM kpi_results ORDER BY created_at DESC LIMIT 15'
        if not filters
        else f'SELECT * FROM kpi_results {where} ORDER BY created_at DESC LIMIT 15',
        params,
    )
    waiters = query_all(
        'SELECT * FROM waiter_metrics ORDER BY business_date DESC, revenue DESC LIMIT 15'
        if not filters
        else f'SELECT * FROM waiter_metrics {where} ORDER BY business_date DESC, revenue DESC LIMIT 15',
        params,
    )

    total_revenue = round(sum(float(row['revenue']) for row in sales), 2)
    total_guests = sum(int(row['guests_count']) for row in sales)
    total_checks = sum(int(row['checks_count']) for row in sales)
    avg_check = round(total_revenue / total_checks, 2) if total_checks else 0
    top_waiter = waiters[0]['waiter_name'] if waiters else None
    latest_manager_kpi = next((row for row in kpi if row['entity_type'] == 'manager'), None)

    return {
        'totals': {
            'revenue': total_revenue,
            'guests': total_guests,
            'checks': total_checks,
            'avg_check': avg_check,
            'top_waiter': top_waiter,
            'latest_manager_kpi': latest_manager_kpi['total_score'] if latest_manager_kpi else None,
        },
        'sales': sales,
        'reports': reports,
        'kpi': kpi,
        'waiters': waiters,
    }


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    message = update.get('message', {})
    chat = message.get('chat', {})
    text = (message.get('text') or '').strip()
    chat_id = chat.get('id')
    user = message.get('from', {})
    full_name = ' '.join(filter(None, [user.get('first_name'), user.get('last_name')])).strip() or 'Manager'

    if not chat_id:
        return {'ok': True}

    if text == '/start':
        web_app_url = f"{APP_BASE_URL}/miniapp?tg_user_id={user.get('id', '')}&full_name={full_name}"
        keyboard = {
            'inline_keyboard': [
                [{'text': 'Открыть Mini App', 'web_app': {'url': web_app_url}}],
                [
                    {'text': 'Синхронизировать demo iiko', 'callback_data': 'sync_demo'},
                    {'text': 'Сводка', 'callback_data': 'summary'},
                ],
            ]
        }
        send_message(chat_id, 'Открой Mini App: отчеты, аналитика, официанты и KPI.', keyboard)
    else:
        send_message(chat_id, 'Напиши /start чтобы открыть меню.')
    return {'ok': True}
