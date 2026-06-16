"""
Analytics API routes for business intelligence and dashboarding.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from app.models.analytics import CostReport, DashboardSummary

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard_summary():
    return DashboardSummary(
        total_content_pieces=0,
        approval_rate=0.95,
        avg_refinement_cycles=0.3,
        avg_generation_latency_ms=4500.0,
        active_clients=12,
        total_revenue=142500.0,
        error_rate_last_hour=0.02,
        top_platforms=[
            {"platform": "twitter", "count": 450},
            {"platform": "linkedin", "count": 380},
            {"platform": "blogspot", "count": 210},
            {"platform": "facebook", "count": 195},
        ],
        cost_forecast_next_30d=875.50,
    )


@router.get("/cost", response_model=CostReport)
async def cost_report(
    days: int = Query(30, ge=1, le=90),
):
    return CostReport(
        period_start=datetime.utcnow() - timedelta(days=days),
        period_end=datetime.utcnow(),
        total_requests=12500,
        total_tokens_input=45000000,
        total_tokens_output=12000000,
        estimated_cost_usd=142.50,
        cost_by_model={
            "gemini-3.1-flash-lite": 0.0,
            "deepseek/deepseek-v4-flash:free": 0.0,
            "nvidia/nemotron-3-super-120b-a12b:free": 0.0,
        },
        cost_by_client={
            "client-alpha": 45.20,
            "client-beta": 32.80,
        },
    )
