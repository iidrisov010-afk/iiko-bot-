import os
import random
from datetime import date, datetime
from typing import Any

import requests

from .db import execute, execute_many, query_all, query_one


class IikoService:
    def __init__(self) -> None:
        self.api_base = os.getenv('IIKO_API_BASE', '').rstrip('/')
        self.api_login = os.getenv('IIKO_API_LOGIN', '')
        self.organization_id = os.getenv('IIKO_ORGANIZATION_ID', '')

    def is_configured(self) -> bool:
        return bool(self.api_base and self.api_login and self.organization_id)

    def sync_daily_stub(self, branch_name: str, business_date: str) -> dict[str, Any]:
        seed = abs(hash(f'{branch_name}-{business_date}')) % 10_000
        rng = random.Random(seed)
        revenue = round(rng.randint(1800000, 4200000), 2)
        checks = rng.randint(60, 150)
        guests = rng.randint(120, 260)
        avg_check = round(revenue / max(checks, 1), 2)
        discounts = round(revenue * rng.uniform(0.01, 0.05), 2)
        deletes = rng.randint(0, 6)
        returns = rng.randint(0, 3)

        metric_id = execute(
            '''
            INSERT INTO iiko_sales_daily (
                branch_name, business_date, revenue, checks_count, guests_count,
                avg_check, discounts_amount, deletes_count, returns_count, source,
                synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                branch_name,
                business_date,
                revenue,
                checks,
                guests,
                avg_check,
                discounts,
                deletes,
                returns,
                'stub',
                datetime.utcnow().isoformat(),
            ),
        )

        waiter_rows: list[tuple[Any, ...]] = []
        waiter_names = ['Ali', 'Bek', 'Jasur', 'Sardor', 'Timur']
        for name in waiter_names:
            waiter_revenue = round(revenue * rng.uniform(0.12, 0.26), 2)
            waiter_checks = rng.randint(10, 35)
            waiter_guests = rng.randint(18, 55)
            waiter_avg_check = round(waiter_revenue / max(waiter_checks, 1), 2)
            upsell_rate = round(rng.uniform(6, 22), 2)
            errors = rng.randint(0, 3)
            guest_score = round(rng.uniform(82, 98), 2)
            waiter_rows.append(
                (
                    branch_name,
                    business_date,
                    name,
                    waiter_revenue,
                    waiter_checks,
                    waiter_guests,
                    waiter_avg_check,
                    upsell_rate,
                    errors,
                    guest_score,
                    metric_id,
                )
            )

        execute_many(
            '''
            INSERT INTO waiter_metrics (
                branch_name, business_date, waiter_name, revenue, checks_count,
                guests_count, avg_check, upsell_rate, errors_count, guest_score,
                source_metric_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            waiter_rows,
        )

        return {
            'metric_id': metric_id,
            'branch_name': branch_name,
            'business_date': business_date,
            'revenue': revenue,
            'checks_count': checks,
            'guests_count': guests,
            'avg_check': avg_check,
            'discounts_amount': discounts,
            'deletes_count': deletes,
            'returns_count': returns,
            'source': 'stub',
        }


class KPIService:
    manager_weights = {
        'report_on_time': 10,
        'revenue_plan': 25,
        'avg_check': 15,
        'guests': 15,
        'service': 15,
        'discipline': 10,
        'standards': 10,
    }

    waiter_weights = {
        'revenue': 30,
        'avg_check': 20,
        'guests': 15,
        'upsell': 15,
        'errors': 10,
        'guest_score': 10,
    }

    @staticmethod
    def clamp(value: float, lower: float = 0, upper: float = 100) -> float:
        return max(lower, min(upper, value))

    def score_ratio(self, fact: float, plan: float) -> float:
        if plan <= 0:
            return 100.0
        return self.clamp((fact / plan) * 100)

    def calc_manager_kpi(self, report: dict[str, Any], sales: dict[str, Any] | None) -> dict[str, Any]:
        plan_revenue = 3000000.0
        plan_avg_check = 25000.0
        plan_guests = 180.0

        fact_revenue = float(sales['revenue']) if sales else 0
        fact_avg_check = float(sales['avg_check']) if sales else float(report.get('avg_check') or 0)
        fact_guests = float(sales['guests_count']) if sales else float(report.get('guests_count') or 0)

        report_on_time = 100.0
        revenue_plan = self.score_ratio(fact_revenue, plan_revenue)
        avg_check_score = self.score_ratio(fact_avg_check, plan_avg_check)
        guest_score = self.score_ratio(fact_guests, plan_guests)
        service = self.clamp(100 - (float(report.get('complaints_count', 0)) * 18) + (float(report.get('compliments_count', 0)) * 4))
        discipline = self.clamp(100 - (float(report.get('discipline_violations', 0)) * 20) - (float(report.get('urgent_incidents', 0)) * 15))
        standards = round((float(report.get('opening_score', 0)) + float(report.get('cleanliness_score', 0))) / 2, 2)

        components = {
            'report_on_time': report_on_time,
            'revenue_plan': revenue_plan,
            'avg_check': avg_check_score,
            'guests': guest_score,
            'service': service,
            'discipline': discipline,
            'standards': standards,
        }
        total = 0.0
        for key, weight in self.manager_weights.items():
            total += components[key] * (weight / 100)
        return {'total_score': round(total, 2), 'components': components}

    def calc_waiter_kpi(self, row: dict[str, Any]) -> dict[str, Any]:
        revenue_score = self.score_ratio(float(row['revenue']), 700000)
        avg_check_score = self.score_ratio(float(row['avg_check']), 25000)
        guests_score = self.score_ratio(float(row['guests_count']), 35)
        upsell_score = self.clamp(float(row['upsell_rate']) * 5)
        errors_score = self.clamp(100 - (float(row['errors_count']) * 25))
        guest_score = self.clamp(float(row['guest_score']))
        components = {
            'revenue': revenue_score,
            'avg_check': avg_check_score,
            'guests': guests_score,
            'upsell': upsell_score,
            'errors': errors_score,
            'guest_score': guest_score,
        }
        total = 0.0
        for key, weight in self.waiter_weights.items():
            total += components[key] * (weight / 100)
        return {'total_score': round(total, 2), 'components': components}

    def rebuild_daily_kpi(self, branch_name: str, business_date: str) -> dict[str, Any]:
        report = query_one(
            '''SELECT * FROM daily_reports WHERE branch_name = ? AND report_date = ? ORDER BY id DESC LIMIT 1''',
            (branch_name, business_date),
        )
        sales = query_one(
            '''SELECT * FROM iiko_sales_daily WHERE branch_name = ? AND business_date = ? ORDER BY id DESC LIMIT 1''',
            (branch_name, business_date),
        )
        if report:
            manager_result = self.calc_manager_kpi(report, sales)
            execute(
                '''
                INSERT INTO kpi_results (
                    business_date, branch_name, entity_type, entity_name, total_score,
                    details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    business_date,
                    branch_name,
                    'manager',
                    report['manager_name'],
                    manager_result['total_score'],
                    str(manager_result['components']),
                    datetime.utcnow().isoformat(),
                ),
            )

        waiter_rows = query_all(
            '''SELECT * FROM waiter_metrics WHERE branch_name = ? AND business_date = ?''',
            (branch_name, business_date),
        )
        waiter_scores: list[dict[str, Any]] = []
        for row in waiter_rows:
            waiter_result = self.calc_waiter_kpi(row)
            waiter_scores.append({'waiter_name': row['waiter_name'], 'score': waiter_result['total_score']})
            execute(
                '''
                INSERT INTO kpi_results (
                    business_date, branch_name, entity_type, entity_name, total_score,
                    details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    business_date,
                    branch_name,
                    'waiter',
                    row['waiter_name'],
                    waiter_result['total_score'],
                    str(waiter_result['components']),
                    datetime.utcnow().isoformat(),
                ),
            )

        return {
            'branch_name': branch_name,
            'business_date': business_date,
            'manager_found': bool(report),
            'waiters_count': len(waiter_rows),
            'waiter_scores': waiter_scores,
        }
