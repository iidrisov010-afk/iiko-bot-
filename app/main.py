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
BOT_TOKEN = "8319602648:AAE-Wf7BB7s05eKlWxYiiACIeaLW5Y8OgeY"
BOT_USERNAME = os.getenv('BOT_USERNAME', 'your_bot_username')
APP_BASE_URL ="https://iiko-bot.onrender.com"
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}' if BOT_TOKEN else ''

app = FastAPI(title='iiko Telegram Mini App v2')
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'app' / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'app' / 'templates'))
iiko_service = IikoService()
kpi_service = KPIService()


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
    init_db()


@app.get("/")
def home():
    return {"status": "ok", "bot": "running"}


@app.get('/miniapp', response_class=HTMLResponse)
def miniapp(request: Request, tg_user_id: Optional[int] = None, full_name: Optional[str] = None):
    return templates.TemplateResponse(
        'miniapp.html',
        {'request': request, 'tg_user_id': tg_user_id or '', 'full_name': full_name or ''},
    )


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


@app.post("/webhook")
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
