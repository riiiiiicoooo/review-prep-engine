"""
FastAPI Backend — REST API for the Review Prep Engine dashboard.

Endpoints:
- GET /households - List all households with engagement scores
- GET /households/{id}/briefing - Get/generate briefing
- GET /households/{id}/action-items - List action items
- POST /households/{id}/action-items/{item_id}/update - Update status
- GET /dashboard/upcoming-reviews - Briefings due in next 2 weeks
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import date, datetime, timedelta
from typing import Optional, List
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.client_profiler import (
    ClientHousehold,
    ClientBook,
    ActionItemStatus,
)
from src.review_assembler import ReviewAssembler
from src.engagement_scorer import EngagementScorer
from storage.json_store import JSONStore

# Initialize app
app = FastAPI(
    title="Review Prep Engine API",
    description="Automated review briefing assembly for wealth management firms",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
store = JSONStore("data")
assembler = ReviewAssembler()
scorer = EngagementScorer()

# Global client book (loaded on startup)
client_book = ClientBook()


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class HouseholdSummary(BaseModel):
    """Summary of a household for listing."""
    id: str
    name: str
    primary_contact: str
    service_tier: str
    advisor: str
    total_aum: float
    aum_change_pct: float
    next_review_date: Optional[str]
    days_until_review: Optional[int]
    engagement_score: Optional[float] = None
    engagement_level: Optional[str] = None
    attrition_risk: Optional[str] = None


class BriefingFlagResponse(BaseModel):
    """A flagged item in a briefing."""
    severity: str
    category: str
    title: str
    detail: str
    recommended_action: Optional[str]


class BriefingResponse(BaseModel):
    """Complete briefing for a household."""
    household_id: str
    household_name: str
    primary_contact: str
    service_tier: str
    advisor: str
    meeting_date: Optional[str]
    last_review_date: Optional[str]
    client_since: Optional[str]
    relationship_years: Optional[int]
    status: str
    assembled_at: str

    high_priority_flags: int
    medium_priority_flags: int
    flags: List[BriefingFlagResponse]

    life_events: List[dict]
    portfolio_summary: Optional[dict]
    goals: List[dict]
    compliance_items: List[dict]
    action_items: List[dict]
    conversation_starters: List[str]

    document_text: str


class ActionItemResponse(BaseModel):
    """Action item with current status."""
    id: str
    description: str
    assigned_to: str
    priority: str
    status: str
    created_date: str
    due_date: Optional[str]
    is_overdue: bool
    days_overdue: int
    source_meeting: Optional[str]
    notes: str


class ActionItemUpdateRequest(BaseModel):
    """Update request for action item status."""
    new_status: str = Field(..., description="New status: open, in_progress, completed, deferred, cancelled")
    notes: Optional[str] = None


class UpcomingReviewCard(BaseModel):
    """Card for upcoming review in dashboard."""
    household_id: str
    household_name: str
    primary_contact: str
    service_tier: str
    advisor: str
    meeting_date: str
    engagement_score: Optional[float]
    engagement_level: Optional[str]
    high_flags: int
    medium_flags: int
    status: str


class DashboardResponse(BaseModel):
    """Dashboard summary for upcoming reviews."""
    upcoming_count: int
    high_priority_flags: int
    medium_priority_flags: int
    total_aum_at_risk: float
    briefings: List[UpcomingReviewCard]


class HouseholdListResponse(BaseModel):
    """List of households with summary data."""
    total_households: int
    total_aum: float
    by_tier: dict
    households: List[HouseholdSummary]


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None


# ============================================================================
# Utility Functions
# ============================================================================

def load_sample_data():
    """Load sample data into client book (for demo)."""
    # For production, this would load from database or API
    # For now, we'll load from storage if it exists
    household_ids = store.list_households()
    for hh_id in household_ids:
        household = store.load_household(hh_id)
        if household:
            client_book.add(household)


def get_household_or_404(household_id: str) -> ClientHousehold:
    """Get household or raise 404."""
    household = client_book.get(household_id)
    if not household:
        raise HTTPException(status_code=404, detail=f"Household {household_id} not found")
    return household


# ============================================================================
# Endpoints
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Load data on startup."""
    load_sample_data()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "households": len(client_book.list_all()),
        "total_aum": f"${client_book.total_aum:,.0f}",
    }


@app.get("/households", response_model=HouseholdListResponse)
async def list_households(
    advisor: Optional[str] = Query(None, description="Filter by advisor name"),
    tier: Optional[str] = Query(None, description="Filter by service tier (platinum, gold, silver)"),
):
    """List all households with summary data and engagement scores."""

    households = client_book.list_all()

    # Filter by advisor if specified
    if advisor:
        households = [h for h in households if h.primary_advisor.lower() == advisor.lower()]

    # Filter by tier if specified
    if tier:
        households = [h for h in households if h.service_tier.value == tier.lower()]

    # Score engagement for all households
    engagement_reports = {}
    for report in scorer.score_book(client_book):
        engagement_reports[report.household_id] = report

    # Build response summaries
    summaries = []
    for hh in households:
        engagement = engagement_reports.get(hh.id)
        summary = HouseholdSummary(
            id=hh.id,
            name=hh.household_name,
            primary_contact=hh.primary_member.name if hh.primary_member else "Unknown",
            service_tier=hh.service_tier.value,
            advisor=hh.primary_advisor,
            total_aum=hh.total_aum,
            aum_change_pct=round(hh.aum_change_pct, 1),
            next_review_date=hh.next_review_date.isoformat() if hh.next_review_date else None,
            days_until_review=hh.days_until_next_review,
            engagement_score=engagement.composite_score if engagement else None,
            engagement_level=engagement.engagement_level.value if engagement else None,
            attrition_risk=engagement.attrition_risk if engagement else None,
        )
        summaries.append(summary)

    return HouseholdListResponse(
        total_households=len(summaries),
        total_aum=client_book.total_aum,
        by_tier={
            "platinum": len([h for h in summaries if h.service_tier == "platinum"]),
            "gold": len([h for h in summaries if h.service_tier == "gold"]),
            "silver": len([h for h in summaries if h.service_tier == "silver"]),
        },
        households=summaries,
    )


@app.get("/households/{household_id}/briefing", response_model=BriefingResponse)
async def get_briefing(household_id: str):
    """Get or generate briefing for a household."""

    household = get_household_or_404(household_id)

    # Try to load from storage first
    briefing = store.load_briefing(household_id)

    # If not found or stale, assemble new one
    if not briefing or briefing.status.value == "not_started":
        briefing = assembler.assemble(household)
        store.save_briefing(briefing)

    # Convert flags to response format
    flags_response = []
    for flag in briefing.flags:
        flags_response.append(BriefingFlagResponse(
            severity=flag.severity.value,
            category=flag.category,
            title=flag.title,
            detail=flag.detail,
            recommended_action=flag.recommended_action,
        ))

    # Build portfolio summary dict
    portfolio_dict = None
    if briefing.portfolio:
        p = briefing.portfolio
        portfolio_dict = {
            "total_aum": p.total_aum,
            "aum_change": p.aum_change,
            "aum_change_pct": p.aum_change_pct,
            "period_return_pct": p.period_return_pct,
            "benchmark_return_pct": p.benchmark_return_pct,
            "excess_return_pct": p.excess_return_pct,
            "benchmark_name": p.benchmark_name,
            "allocation": p.allocation_summary,
            "rebalance_needed": p.rebalance_needed,
            "rebalance_items": p.rebalance_items,
        }

    # Build compliance dict
    compliance_dict = None
    if briefing.compliance:
        compliance_dict = {
            "overall_status": briefing.compliance.overall_status,
            "items": briefing.compliance.items,
            "action_required": briefing.compliance.action_required,
        }

    return BriefingResponse(
        household_id=briefing.household_id,
        household_name=briefing.household_name,
        primary_contact=briefing.primary_contact,
        service_tier=briefing.service_tier,
        advisor=briefing.advisor,
        meeting_date=briefing.meeting_date.isoformat() if briefing.meeting_date else None,
        last_review_date=briefing.last_review_date.isoformat() if briefing.last_review_date else None,
        client_since=briefing.client_since.isoformat() if briefing.client_since else None,
        relationship_years=briefing.relationship_years,
        status=briefing.status.value,
        assembled_at=briefing.assembled_at.isoformat(),
        high_priority_flags=briefing.high_priority_count,
        medium_priority_flags=briefing.medium_priority_count,
        flags=flags_response,
        life_events=briefing.life_events,
        portfolio_summary=portfolio_dict,
        goals=briefing.goals,
        compliance_items=briefing.compliance.items if briefing.compliance else [],
        action_items=briefing.action_items,
        conversation_starters=briefing.conversation_starters,
        document_text=briefing.document_text,
    )


@app.get("/households/{household_id}/action-items", response_model=List[ActionItemResponse])
async def get_action_items(household_id: str):
    """List open action items for a household."""

    household = get_household_or_404(household_id)

    items = []
    for ai in household.action_items:
        if ai.status != ActionItemStatus.COMPLETED and ai.status != ActionItemStatus.CANCELLED:
            items.append(ActionItemResponse(
                id=ai.id,
                description=ai.description,
                assigned_to=ai.assigned_to,
                priority=ai.priority.value,
                status=ai.status.value,
                created_date=ai.created_date.isoformat(),
                due_date=ai.due_date.isoformat() if ai.due_date else None,
                is_overdue=ai.is_overdue,
                days_overdue=ai.days_overdue,
                source_meeting=ai.source_meeting,
                notes=ai.notes,
            ))

    return items


@app.post("/households/{household_id}/action-items/{item_id}/update")
async def update_action_item(
    household_id: str,
    item_id: str,
    request: ActionItemUpdateRequest,
):
    """Update status of an action item."""

    household = get_household_or_404(household_id)

    # Find the action item
    action_item = None
    for ai in household.action_items:
        if ai.id == item_id:
            action_item = ai
            break

    if not action_item:
        raise HTTPException(status_code=404, detail=f"Action item {item_id} not found")

    # Update status
    try:
        new_status = ActionItemStatus[request.new_status.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: open, in_progress, completed, deferred, cancelled"
        )

    action_item.status = new_status
    if new_status == ActionItemStatus.COMPLETED:
        action_item.completed_date = date.today()

    # Save household
    store.save_household(household)

    # Track in action item tracker
    store.update_action_item_status(item_id, new_status, request.notes or "")

    return {
        "status": "updated",
        "action_item_id": item_id,
        "new_status": new_status.value,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/dashboard/upcoming-reviews", response_model=DashboardResponse)
async def get_upcoming_reviews(
    within_days: int = Query(14, description="Days ahead to look for upcoming reviews"),
):
    """Get briefings due within N days."""

    due_households = client_book.list_reviews_due(within_days)
    overdue_households = client_book.list_overdue_reviews()

    # Combine and deduplicate
    households = {h.id: h for h in due_households + overdue_households}

    # Score engagement
    engagement_reports = {}
    for report in scorer.score_book(client_book):
        engagement_reports[report.household_id] = report

    # Assemble briefings
    cards = []
    total_high_flags = 0
    total_medium_flags = 0
    total_aum_at_risk = 0

    for hh in sorted(households.values(), key=lambda h: h.next_review_date or date.max):
        briefing = assembler.assemble(hh)
        engagement = engagement_reports.get(hh.id)

        total_high_flags += briefing.high_priority_count
        total_medium_flags += briefing.medium_priority_count

        if engagement and engagement.attrition_risk in ("high", "critical"):
            total_aum_at_risk += hh.total_aum

        card = UpcomingReviewCard(
            household_id=hh.id,
            household_name=hh.household_name,
            primary_contact=hh.primary_member.name if hh.primary_member else "Unknown",
            service_tier=hh.service_tier.value,
            advisor=hh.primary_advisor,
            meeting_date=str(hh.next_review_date or date.today()),
            engagement_score=engagement.composite_score if engagement else None,
            engagement_level=engagement.engagement_level.value if engagement else None,
            high_flags=briefing.high_priority_count,
            medium_flags=briefing.medium_priority_count,
            status=briefing.status.value,
        )
        cards.append(card)

    return DashboardResponse(
        upcoming_count=len(cards),
        high_priority_flags=total_high_flags,
        medium_priority_flags=total_medium_flags,
        total_aum_at_risk=total_aum_at_risk,
        briefings=cards,
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Review Prep Engine API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "GET /households": "List all households",
            "GET /households/{id}/briefing": "Get/generate briefing",
            "GET /households/{id}/action-items": "List action items",
            "POST /households/{id}/action-items/{item_id}/update": "Update action item status",
            "GET /dashboard/upcoming-reviews": "Briefings due in next N days",
        }
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
