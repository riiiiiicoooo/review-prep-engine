"""
Review Assembler — Builds the advisor-ready briefing from client profile data.

This is the module that replaced 45 minutes of copy-pasting from 4 systems.
It reads the client profile and produces a structured briefing document
that highlights what's changed, what's overdue, and what needs discussion.

The key insight: advisors don't need a data dump. They need a delta.
"What's different since the last time I sat with this client?" That's
the question this module answers.

The briefing is organized in the order advisors actually run meetings:
1. Quick context (who am I meeting with, what tier, how long have they been a client)
2. What's changed (life events, AUM movement, goal status)
3. Portfolio review (performance, allocation, rebalancing needs)
4. Planning items (compliance, financial plan currency, documents)
5. Open items (action items from last meeting, overdue follow-ups)
6. Conversation starters (things to ask about based on life events and notes)
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional
from enum import Enum

from client_profiler import (
    ClientHousehold,
    ClientBook,
    ServiceTier,
    LifeEvent,
    LifeEventCategory,
    ComplianceDocument,
    DocumentType,
    ActionItem,
    ActionItemStatus,
    GoalStatus,
    AssetAllocation,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BriefingStatus(Enum):
    """Prep status for an upcoming review."""
    NOT_STARTED = "not_started"
    AUTO_ASSEMBLED = "auto_assembled"  # System built it, needs human review
    REVIEWED = "reviewed"              # Paraplanner verified
    APPROVED = "approved"              # Advisor signed off
    MEETING_COMPLETE = "meeting_complete"


class FlagSeverity(Enum):
    """How important a flagged item is."""
    HIGH = "high"        # Must discuss in the meeting
    MEDIUM = "medium"    # Should discuss if time permits
    LOW = "low"          # Nice to know


# ---------------------------------------------------------------------------
# Briefing Data Models
# ---------------------------------------------------------------------------

@dataclass
class BriefingFlag:
    """A flagged item for the advisor's attention."""
    severity: FlagSeverity
    category: str          # "life_event", "compliance", "action_item", "performance", "goal"
    title: str
    detail: str
    recommended_action: Optional[str] = None


@dataclass
class PortfolioSummary:
    """Portfolio section of the briefing."""
    total_aum: float
    aum_at_last_review: float
    aum_change: float
    aum_change_pct: float

    # Performance
    period_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    benchmark_name: str

    # Allocation
    allocation_summary: list[dict]     # [{asset_class, target, actual, drift, needs_rebalance}]
    rebalance_needed: bool
    rebalance_items: list[str]         # Human-readable rebalance actions

    # Net flows
    net_flows: float


@dataclass
class ComplianceCheck:
    """Compliance section of the briefing."""
    overall_status: str                # "current", "expiring_soon", "action_required"
    items: list[dict]                  # [{document_type, status, last_completed, expiration, note}]
    action_required: list[dict]        # Only items needing attention


@dataclass
class ReviewBriefing:
    """The complete advisor-ready briefing for a client meeting.

    This is the deliverable. The paraplanner reviews it for accuracy,
    the advisor reads it before the meeting.
    """
    # Header
    household_id: str
    household_name: str
    primary_contact: str
    service_tier: str
    advisor: str
    meeting_date: Optional[date]
    last_review_date: Optional[date]
    client_since: Optional[date]
    relationship_years: Optional[int]

    # Status
    status: BriefingStatus
    assembled_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Flags (the most important part)
    flags: list[BriefingFlag] = field(default_factory=list)
    high_priority_count: int = 0
    medium_priority_count: int = 0

    # Sections
    household_context: dict = field(default_factory=dict)
    life_events: list[dict] = field(default_factory=list)
    portfolio: Optional[PortfolioSummary] = None
    goals: list[dict] = field(default_factory=list)
    compliance: Optional[ComplianceCheck] = None
    action_items: list[dict] = field(default_factory=list)
    conversation_starters: list[str] = field(default_factory=list)

    # Document output
    document_text: str = ""


# ---------------------------------------------------------------------------
# Review Assembler
# ---------------------------------------------------------------------------

class ReviewAssembler:
    """Builds review briefings from client profiles.

    Call assemble() with a household and a meeting date, and it produces
    a complete ReviewBriefing with flags, portfolio summary, compliance
    checks, and conversation starters.
    """

    def assemble(
        self,
        household: ClientHousehold,
        meeting_date: Optional[date] = None,
    ) -> ReviewBriefing:
        """Assemble a complete review briefing for a client household."""

        meeting_date = meeting_date or household.next_review_date or date.today()

        briefing = ReviewBriefing(
            household_id=household.id,
            household_name=household.household_name,
            primary_contact=household.primary_member.name if household.primary_member else "Unknown",
            service_tier=household.service_tier.value,
            advisor=household.primary_advisor,
            meeting_date=meeting_date,
            last_review_date=household.last_review_date,
            client_since=household.client_since,
            relationship_years=(
                (date.today().year - household.client_since.year)
                if household.client_since else None
            ),
            status=BriefingStatus.AUTO_ASSEMBLED,
            assembled_at=datetime.now(),
        )

        # Build each section
        briefing.household_context = self._build_household_context(household)
        briefing.life_events = self._build_life_events(household)
        briefing.portfolio = self._build_portfolio_summary(household)
        briefing.goals = self._build_goals(household)
        briefing.compliance = self._build_compliance(household)
        briefing.action_items = self._build_action_items(household)
        briefing.conversation_starters = self._generate_conversation_starters(household)

        # Generate flags from all sections
        briefing.flags = self._generate_flags(household, briefing)
        briefing.high_priority_count = len(
            [f for f in briefing.flags if f.severity == FlagSeverity.HIGH]
        )
        briefing.medium_priority_count = len(
            [f for f in briefing.flags if f.severity == FlagSeverity.MEDIUM]
        )

        # Generate document text
        briefing.document_text = self._format_briefing(briefing)

        return briefing

    # -- Section Builders ---------------------------------------------------

    def _build_household_context(self, hh: ClientHousehold) -> dict:
        members = []
        for m in hh.members:
            info = {
                "name": m.name,
                "relationship": m.relationship,
                "age": m.age,
                "occupation": m.occupation or "N/A",
                "retired": m.is_retired,
            }
            if m.is_retired and m.retirement_date:
                info["retired_since"] = m.retirement_date.isoformat()
            members.append(info)

        return {
            "members": members,
            "risk_tolerance": hh.risk_tolerance,
            "investment_objective": hh.investment_objective,
            "time_horizon": hh.time_horizon,
            "total_accounts": len(hh.accounts),
            "managed_accounts": len(hh.managed_accounts),
        }

    def _build_life_events(self, hh: ClientHousehold) -> list[dict]:
        events = hh.events_since_last_review()
        return [
            {
                "category": e.category.value,
                "description": e.description,
                "date": e.event_date.isoformat(),
                "member": e.household_member,
                "planning_impact": e.planning_impact,
                "follow_up_needed": e.follow_up_needed,
            }
            for e in sorted(events, key=lambda x: x.event_date, reverse=True)
        ]

    def _build_portfolio_summary(self, hh: ClientHousehold) -> PortfolioSummary:
        # Get most recent performance snapshot
        perf = hh.performance[0] if hh.performance else None

        # Allocation analysis
        alloc_summary = []
        rebalance_items = []
        for a in hh.asset_allocation:
            item = {
                "asset_class": a.asset_class,
                "target_pct": a.target_pct,
                "actual_pct": a.actual_pct,
                "drift_pct": round(a.drift_pct, 1),
                "market_value": a.market_value,
                "needs_rebalance": a.needs_rebalance,
            }
            alloc_summary.append(item)
            if a.needs_rebalance:
                direction = "overweight" if a.drift_pct > 0 else "underweight"
                rebalance_items.append(
                    f"{a.asset_class}: {direction} by {abs(a.drift_pct):.1f}%"
                )

        return PortfolioSummary(
            total_aum=hh.total_aum,
            aum_at_last_review=hh.total_aum_previous,
            aum_change=hh.aum_change,
            aum_change_pct=round(hh.aum_change_pct, 1),
            period_return_pct=perf.portfolio_return_pct if perf else 0,
            benchmark_return_pct=perf.benchmark_return_pct if perf else 0,
            excess_return_pct=perf.excess_return_pct if perf else 0,
            benchmark_name=perf.benchmark_name if perf else "N/A",
            allocation_summary=alloc_summary,
            rebalance_needed=len(rebalance_items) > 0,
            rebalance_items=rebalance_items,
            net_flows=perf.net_flows if perf else 0,
        )

    def _build_goals(self, hh: ClientHousehold) -> list[dict]:
        return [
            {
                "name": g.name,
                "category": g.category,
                "status": g.status.value,
                "funded_pct": g.current_funded_pct,
                "target_amount": g.target_amount,
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "last_reviewed": g.last_reviewed.isoformat() if g.last_reviewed else None,
                "notes": g.notes,
            }
            for g in hh.goals
        ]

    def _build_compliance(self, hh: ClientHousehold) -> ComplianceCheck:
        items = []
        action_required = []

        for doc in hh.documents:
            item = {
                "document_type": doc.document_type.value,
                "status": doc.status,
                "last_completed": doc.last_completed.isoformat() if doc.last_completed else None,
                "expiration": doc.expiration_date.isoformat() if doc.expiration_date else None,
                "days_until_expiry": doc.days_until_expiry,
                "notes": doc.notes,
            }
            items.append(item)

            if doc.is_expired or doc.is_expiring_soon or doc.status == "missing":
                action_required.append(item)

        return ComplianceCheck(
            overall_status=hh.compliance_status,
            items=items,
            action_required=action_required,
        )

    def _build_action_items(self, hh: ClientHousehold) -> list[dict]:
        return [
            {
                "id": a.id,
                "description": a.description,
                "assigned_to": a.assigned_to,
                "status": a.status.value,
                "priority": a.priority.value,
                "created_date": a.created_date.isoformat(),
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "is_overdue": a.is_overdue,
                "days_overdue": a.days_overdue,
                "source_meeting": a.source_meeting,
                "notes": a.notes,
            }
            for a in hh.action_items
            if a.status not in (ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED)
        ]

    # -- Flag Generation ----------------------------------------------------

    def _generate_flags(
        self, hh: ClientHousehold, briefing: ReviewBriefing
    ) -> list[BriefingFlag]:
        """Generate attention flags across all sections."""
        flags = []

        # Life event flags
        for event in hh.events_since_last_review():
            severity = FlagSeverity.HIGH if event.category in (
                LifeEventCategory.DEATH_FAMILY,
                LifeEventCategory.DIVORCE,
                LifeEventCategory.RETIREMENT,
                LifeEventCategory.HEALTH_ISSUE,
                LifeEventCategory.INHERITANCE,
            ) else FlagSeverity.MEDIUM

            flags.append(BriefingFlag(
                severity=severity,
                category="life_event",
                title=f"Life event: {event.category.value.replace('_', ' ').title()}",
                detail=event.description,
                recommended_action=event.planning_impact,
            ))

        # Compliance flags
        for doc in hh.compliance_issues:
            if doc.is_expired or doc.status == "missing":
                flags.append(BriefingFlag(
                    severity=FlagSeverity.HIGH,
                    category="compliance",
                    title=f"{doc.document_type.value.upper()} expired or missing",
                    detail=f"Last completed: {doc.last_completed}. {doc.notes}",
                    recommended_action="Complete during or immediately after this meeting.",
                ))
            elif doc.is_expiring_soon:
                flags.append(BriefingFlag(
                    severity=FlagSeverity.MEDIUM,
                    category="compliance",
                    title=f"{doc.document_type.value.upper()} expiring in {doc.days_until_expiry} days",
                    detail=doc.notes or "Schedule renewal.",
                ))

        # Action item flags
        overdue = hh.overdue_action_items
        if overdue:
            for item in overdue:
                flags.append(BriefingFlag(
                    severity=FlagSeverity.HIGH,
                    category="action_item",
                    title=f"Overdue action item ({item.days_overdue} days): {item.description}",
                    detail=f"Assigned to {item.assigned_to}. From {item.source_meeting or 'unknown meeting'}.",
                    recommended_action="Address in meeting. Client will likely ask about this.",
                ))

        # Goal flags
        at_risk = [g for g in hh.goals if g.status == GoalStatus.AT_RISK]
        for goal in at_risk:
            flags.append(BriefingFlag(
                severity=FlagSeverity.MEDIUM,
                category="goal",
                title=f"Goal at risk: {goal.name}",
                detail=f"{goal.current_funded_pct}% funded. {goal.notes}",
                recommended_action="Review funding strategy and timeline.",
            ))

        # Financial plan staleness
        plan_doc = next(
            (d for d in hh.documents if d.document_type == DocumentType.FINANCIAL_PLAN),
            None,
        )
        if plan_doc and plan_doc.last_completed:
            months_old = (date.today() - plan_doc.last_completed).days / 30
            if months_old > 12:
                flags.append(BriefingFlag(
                    severity=FlagSeverity.HIGH,
                    category="compliance",
                    title=f"Financial plan is {int(months_old)} months old",
                    detail=plan_doc.notes or "Plan may not reflect current circumstances.",
                    recommended_action="Schedule plan update meeting.",
                ))

        # Rebalance flag
        if briefing.portfolio and briefing.portfolio.rebalance_needed:
            flags.append(BriefingFlag(
                severity=FlagSeverity.MEDIUM,
                category="performance",
                title="Portfolio rebalance needed",
                detail="; ".join(briefing.portfolio.rebalance_items),
                recommended_action="Discuss rebalancing strategy in meeting.",
            ))

        # Sort by severity
        severity_order = {FlagSeverity.HIGH: 0, FlagSeverity.MEDIUM: 1, FlagSeverity.LOW: 2}
        flags.sort(key=lambda f: severity_order[f.severity])

        return flags

    # -- Conversation Starters ----------------------------------------------

    def _generate_conversation_starters(
        self, hh: ClientHousehold
    ) -> list[str]:
        """Generate natural conversation topics based on client context.

        These are the things that make a client feel known. "How's
        Margaret enjoying retirement?" instead of going straight into
        portfolio performance.
        """
        starters = []

        for event in hh.events_since_last_review():
            if event.category == LifeEventCategory.RETIREMENT:
                member = event.household_member or "the family member"
                starters.append(
                    f"Ask how {member} is adjusting to retirement. "
                    f"Any changes to spending patterns or lifestyle plans?"
                )
            elif event.category == LifeEventCategory.DEATH_FAMILY:
                starters.append(
                    "Express condolences if not already done in person. "
                    "Ask about estate/probate timeline — don't push, just open the door."
                )
            elif event.category == LifeEventCategory.BIRTH_GRANDCHILD:
                starters.append(
                    "Congratulate on the grandchild. Natural segue into "
                    "529 plan or gifting strategy conversation."
                )
            elif event.category == LifeEventCategory.JOB_CHANGE:
                starters.append(
                    f"Ask about the new role. Check on 401(k) rollover from "
                    f"previous employer and benefits enrollment timeline."
                )
            elif event.category == LifeEventCategory.HOME_PURCHASE:
                starters.append(
                    "Ask about the new home. Discuss homeowner's insurance, "
                    "mortgage strategy, and impact on cash flow."
                )

        # Goal-based starters
        for goal in hh.goals:
            if goal.status == GoalStatus.AT_RISK:
                starters.append(
                    f"'{goal.name}' is at risk ({goal.current_funded_pct}% funded). "
                    f"Discuss whether to adjust the target, timeline, or contributions."
                )

        # Engagement-based starters
        if hh.last_review_date:
            months_since = (date.today() - hh.last_review_date).days / 30
            if months_since > 8:
                starters.append(
                    f"It's been {int(months_since)} months since the last review. "
                    f"Check in on any major changes not captured in notes."
                )

        return starters

    # -- Document Formatting ------------------------------------------------

    def _format_briefing(self, briefing: ReviewBriefing) -> str:
        """Format the briefing as a readable text document."""
        lines = []
        lines.append("=" * 60)
        lines.append("CLIENT REVIEW BRIEFING")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Client:       {briefing.household_name}")
        lines.append(f"Contact:      {briefing.primary_contact}")
        lines.append(f"Tier:         {briefing.service_tier.upper()}")
        lines.append(f"Advisor:      {briefing.advisor}")
        lines.append(f"Meeting:      {briefing.meeting_date}")
        lines.append(f"Last Review:  {briefing.last_review_date}")
        if briefing.relationship_years:
            lines.append(f"Client Since: {briefing.client_since} ({briefing.relationship_years} years)")
        lines.append("")

        # Flags
        if briefing.flags:
            lines.append("-" * 60)
            lines.append(f"ATTENTION FLAGS ({briefing.high_priority_count} high, {briefing.medium_priority_count} medium)")
            lines.append("-" * 60)
            lines.append("")
            for flag in briefing.flags:
                icon = "!!!" if flag.severity == FlagSeverity.HIGH else " ! "
                lines.append(f"  [{icon}] {flag.title}")
                lines.append(f"         {flag.detail}")
                if flag.recommended_action:
                    lines.append(f"         Action: {flag.recommended_action}")
                lines.append("")

        # Household
        lines.append("-" * 60)
        lines.append("HOUSEHOLD")
        lines.append("-" * 60)
        lines.append("")
        for m in briefing.household_context.get("members", []):
            retired_note = " (retired)" if m.get("retired") else ""
            lines.append(f"  {m['name']} — {m['relationship']}, age {m.get('age', 'N/A')}, {m['occupation']}{retired_note}")
        lines.append(f"\n  Risk tolerance: {briefing.household_context.get('risk_tolerance', 'N/A')}")
        lines.append(f"  Objective: {briefing.household_context.get('investment_objective', 'N/A')}")
        lines.append("")

        # Life events
        if briefing.life_events:
            lines.append("-" * 60)
            lines.append("LIFE EVENTS SINCE LAST REVIEW")
            lines.append("-" * 60)
            lines.append("")
            for event in briefing.life_events:
                lines.append(f"  [{event['date']}] {event['category'].upper()}")
                lines.append(f"  {event['description']}")
                if event.get("planning_impact"):
                    lines.append(f"  Planning impact: {event['planning_impact']}")
                lines.append("")

        # Portfolio
        if briefing.portfolio:
            p = briefing.portfolio
            lines.append("-" * 60)
            lines.append("PORTFOLIO SUMMARY")
            lines.append("-" * 60)
            lines.append("")
            lines.append(f"  AUM:              ${p.total_aum:>12,.0f}")
            lines.append(f"  At last review:   ${p.aum_at_last_review:>12,.0f}")
            lines.append(f"  Change:           ${p.aum_change:>12,.0f} ({p.aum_change_pct:+.1f}%)")
            if p.net_flows != 0:
                lines.append(f"  Net flows:        ${p.net_flows:>12,.0f}")
            lines.append("")
            lines.append(f"  Return (period):  {p.period_return_pct:+.1f}%")
            lines.append(f"  Benchmark ({p.benchmark_name}): {p.benchmark_return_pct:+.1f}%")
            lines.append(f"  Excess return:    {p.excess_return_pct:+.1f}%")
            lines.append("")

            if p.allocation_summary:
                lines.append("  Asset Allocation:")
                lines.append(f"  {'Class':<25} {'Target':>8} {'Actual':>8} {'Drift':>8}")
                lines.append(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8}")
                for a in p.allocation_summary:
                    flag = " *" if a["needs_rebalance"] else ""
                    lines.append(
                        f"  {a['asset_class']:<25} {a['target_pct']:>7.1f}% {a['actual_pct']:>7.1f}% {a['drift_pct']:>+7.1f}%{flag}"
                    )
                if p.rebalance_needed:
                    lines.append(f"\n  * Rebalance recommended")
            lines.append("")

        # Goals
        if briefing.goals:
            lines.append("-" * 60)
            lines.append("FINANCIAL GOALS")
            lines.append("-" * 60)
            lines.append("")
            for g in briefing.goals:
                status_icon = {
                    "on_track": "[OK]", "at_risk": "[!!]",
                    "off_track": "[XX]", "achieved": "[**]", "deferred": "[--]",
                }[g["status"]]
                lines.append(f"  {status_icon} {g['name']}")
                if g.get("target_amount"):
                    lines.append(f"       Target: ${g['target_amount']:,.0f} by {g.get('target_date', 'TBD')}")
                lines.append(f"       Funded: {g['funded_pct']}%")
                if g.get("notes"):
                    lines.append(f"       Note: {g['notes']}")
                lines.append("")

        # Compliance
        if briefing.compliance and briefing.compliance.action_required:
            lines.append("-" * 60)
            lines.append("COMPLIANCE — ACTION REQUIRED")
            lines.append("-" * 60)
            lines.append("")
            for item in briefing.compliance.action_required:
                lines.append(f"  {item['document_type'].upper()}: {item['status']}")
                if item.get("expiration"):
                    lines.append(f"  Expires: {item['expiration']}")
                if item.get("notes"):
                    lines.append(f"  Note: {item['notes']}")
                lines.append("")

        # Action items
        if briefing.action_items:
            lines.append("-" * 60)
            lines.append("OPEN ACTION ITEMS")
            lines.append("-" * 60)
            lines.append("")
            for item in briefing.action_items:
                overdue_tag = f" — {item['days_overdue']} DAYS OVERDUE" if item["is_overdue"] else ""
                lines.append(f"  [{item['priority'].upper()}] {item['description']}{overdue_tag}")
                lines.append(f"         Assigned: {item['assigned_to']} | From: {item.get('source_meeting', 'N/A')}")
                if item.get("notes"):
                    lines.append(f"         Note: {item['notes']}")
                lines.append("")

        # Conversation starters
        if briefing.conversation_starters:
            lines.append("-" * 60)
            lines.append("CONVERSATION STARTERS")
            lines.append("-" * 60)
            lines.append("")
            for i, starter in enumerate(briefing.conversation_starters, 1):
                lines.append(f"  {i}. {starter}")
            lines.append("")

        return "\n".join(lines)

    # -- Batch Assembly -----------------------------------------------------

    def assemble_upcoming(
        self, book: ClientBook, within_days: int = 14
    ) -> list[ReviewBriefing]:
        """Assemble briefings for all reviews due within N days."""
        due = book.list_reviews_due(within_days)
        overdue = book.list_overdue_reviews()

        # Combine, deduplicate
        households = {h.id: h for h in due + overdue}

        briefings = []
        for hh in households.values():
            briefing = self.assemble(hh)
            briefings.append(briefing)

        # Sort by meeting date
        briefings.sort(key=lambda b: b.meeting_date or date.max)
        return briefings

    def get_prep_dashboard(
        self, briefings: list[ReviewBriefing]
    ) -> dict:
        """Summary for the paraplanner dashboard."""
        return {
            "total_upcoming": len(briefings),
            "status_counts": {
                "not_started": len([b for b in briefings if b.status == BriefingStatus.NOT_STARTED]),
                "auto_assembled": len([b for b in briefings if b.status == BriefingStatus.AUTO_ASSEMBLED]),
                "reviewed": len([b for b in briefings if b.status == BriefingStatus.REVIEWED]),
                "approved": len([b for b in briefings if b.status == BriefingStatus.APPROVED]),
            },
            "total_high_flags": sum(b.high_priority_count for b in briefings),
            "total_medium_flags": sum(b.medium_priority_count for b in briefings),
            "briefings": [
                {
                    "household": b.household_name,
                    "meeting_date": b.meeting_date.isoformat() if b.meeting_date else None,
                    "tier": b.service_tier,
                    "high_flags": b.high_priority_count,
                    "medium_flags": b.medium_priority_count,
                    "status": b.status.value,
                }
                for b in briefings
            ],
        }


# ---------------------------------------------------------------------------
# Usage Example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Reuse the client book from client_profiler example
    from client_profiler import (
        ClientHousehold, ClientBook, ServiceTier, HouseholdMember, Account,
        AccountType, PerformanceSnapshot, AssetAllocation, LifeEvent,
        LifeEventCategory, FinancialGoal, GoalStatus, ComplianceDocument,
        DocumentType, ActionItem, ActionItemStatus, ActionItemPriority,
        ReviewRecord, Interaction,
    )

    today = date.today()
    book = ClientBook()

    # Henderson household (same as profiler example)
    henderson = ClientHousehold(
        id="HH-001",
        household_name="The Henderson Household",
        service_tier=ServiceTier.GOLD,
        primary_advisor="Michelle Torres",
        client_since=date(2017, 3, 15),
        last_review_date=today - timedelta(days=95),
        next_review_date=today + timedelta(days=12),
        review_frequency="semi_annual",
        risk_tolerance="Moderate Growth",
        investment_objective="Growth with income",
        time_horizon="15-20 years",
        members=[
            HouseholdMember("Robert Henderson", "primary", date(1962, 8, 14),
                            occupation="Small business owner"),
            HouseholdMember("Margaret Henderson", "spouse", date(1964, 11, 2),
                            occupation="Retired teacher", is_retired=True,
                            retirement_date=date(2025, 9, 1)),
        ],
        accounts=[
            Account("ACCT-001", AccountType.JOINT, "Robert & Margaret Henderson",
                    "Schwab", 485000, today, 448000, today - timedelta(days=95)),
            Account("ACCT-002", AccountType.TRADITIONAL_IRA, "Robert Henderson",
                    "Schwab", 312000, today, 289000, today - timedelta(days=95)),
            Account("ACCT-003", AccountType.ROTH_IRA, "Margaret Henderson",
                    "Schwab", 198000, today, 182000, today - timedelta(days=95)),
            Account("ACCT-004", AccountType.ROLLOVER_IRA, "Margaret Henderson",
                    "Schwab", 245000, today, 0, None, date(2025, 9, 15)),
        ],
        performance=[
            PerformanceSnapshot("Since Last Review", today - timedelta(days=95), today,
                                8.3, 7.1, "60/40 Blend", 245000, 919000, 1240000),
        ],
        asset_allocation=[
            AssetAllocation("US Equity", 40.0, 43.2, 535680),
            AssetAllocation("International Equity", 15.0, 14.1, 174840),
            AssetAllocation("Fixed Income", 30.0, 27.8, 344720),
            AssetAllocation("Alternatives", 10.0, 10.4, 128960),
            AssetAllocation("Cash", 5.0, 4.5, 55800),
        ],
        life_events=[
            LifeEvent("LE-001", LifeEventCategory.RETIREMENT,
                      "Margaret retired from teaching after 28 years. Pension: $3,200/mo.",
                      date(2025, 9, 1), date(2025, 9, 5), "Michelle Torres",
                      "Margaret Henderson",
                      "Update financial plan for earlier retirement."),
            LifeEvent("LE-002", LifeEventCategory.DEATH_FAMILY,
                      "Robert's mother passed away. Estate in probate, potential inheritance.",
                      date(2025, 10, 15), date(2025, 10, 18), "Michelle Torres",
                      "Robert Henderson",
                      "Follow up on inheritance amount and timing.",
                      follow_up_needed=True),
        ],
        goals=[
            FinancialGoal("G-001", "Retirement at 65 (Robert)", "retirement",
                          2500000, date(2027, 8, 14), 78.0, GoalStatus.ON_TRACK,
                          today - timedelta(days=95)),
            FinancialGoal("G-002", "College fund for grandson", "education",
                          120000, date(2036, 9, 1), 32.0, GoalStatus.ON_TRACK,
                          today - timedelta(days=95)),
            FinancialGoal("G-003", "Vacation home down payment", "lifestyle",
                          150000, date(2028, 6, 1), 45.0, GoalStatus.AT_RISK,
                          today - timedelta(days=95),
                          notes="May need to re-evaluate given Margaret's retirement"),
        ],
        documents=[
            ComplianceDocument(DocumentType.INVESTMENT_POLICY_STATEMENT,
                               "current", date(2025, 6, 15), date(2026, 6, 15)),
            ComplianceDocument(DocumentType.RISK_TOLERANCE_QUESTIONNAIRE,
                               "current", date(2025, 8, 1), date(2026, 4, 1)),
            ComplianceDocument(DocumentType.FINANCIAL_PLAN,
                               "expiring", date(2024, 11, 20), date(2025, 11, 20), 12,
                               "Stale — predates Margaret's retirement"),
            ComplianceDocument(DocumentType.ADV_PART_2,
                               "current", date(2026, 1, 15), date(2027, 1, 15)),
        ],
        action_items=[
            ActionItem("AI-001", "Research long-term care insurance options",
                       "Michelle Torres", today - timedelta(days=95),
                       today - timedelta(days=65), ActionItemPriority.MEDIUM,
                       ActionItemStatus.OPEN, "Q3 2025 Review"),
            ActionItem("AI-003", "Update beneficiary designations on rollover IRA",
                       "Sarah Kim", today - timedelta(days=60),
                       today - timedelta(days=30), ActionItemPriority.HIGH,
                       ActionItemStatus.OPEN),
        ],
    )
    book.add(henderson)

    # Assemble the briefing
    assembler = ReviewAssembler()
    briefing = assembler.assemble(henderson)

    print(briefing.document_text)

    print("\n" + "=" * 60)
    print("PREP DASHBOARD")
    print("=" * 60)
    briefings = assembler.assemble_upcoming(book, within_days=30)
    dashboard = assembler.get_prep_dashboard(briefings)
    print(f"\nUpcoming reviews: {dashboard['total_upcoming']}")
    print(f"High-priority flags: {dashboard['total_high_flags']}")
    for b in dashboard["briefings"]:
        print(f"  {b['household']}: {b['meeting_date']} [{b['tier']}] — {b['high_flags']} high, {b['medium_flags']} medium flags")
