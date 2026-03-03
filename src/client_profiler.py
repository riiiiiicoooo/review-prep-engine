"""
Client Profiler — The single client view that didn't exist before.

Before this module, client data lived in 4 places:
- Salesforce: contact info, notes, meeting history
- Black Diamond: portfolio performance, holdings, account balances
- MoneyGuidePro: financial plan, goals, projections
- A compliance spreadsheet: IPS dates, risk tolerance, ADV delivery

Nobody had a complete picture. The advisor had to mentally stitch together
information from all four systems during the meeting.

This module creates the unified client profile that everything else
(review_assembler, engagement_scorer) reads from.

Design constraint: same as scope-tracker. No ORM, no database deps.
The firm's infrastructure is Salesforce + cloud apps + a shared drive.
This runs on dataclasses and could persist to JSON.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional
from collections import defaultdict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ServiceTier(Enum):
    """Client service level based on AUM. Determines review frequency."""
    PLATINUM = "platinum"    # >$2M AUM, quarterly reviews
    GOLD = "gold"            # $500k-$2M, semi-annual reviews
    SILVER = "silver"        # <$500k, annual reviews


class AccountType(Enum):
    """Investment account types."""
    INDIVIDUAL = "individual"
    JOINT = "joint"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    SEP_IRA = "sep_ira"
    ROLLOVER_IRA = "rollover_ira"
    TRUST = "trust"
    ESTATE = "estate"
    CUSTODIAL = "custodial"       # UTMA/UGMA
    EDUCATION_529 = "529"
    CORPORATE = "corporate"
    PENSION = "pension"


class LifeEventCategory(Enum):
    """Major life events that affect financial planning."""
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    BIRTH_CHILD = "birth_child"
    BIRTH_GRANDCHILD = "birth_grandchild"
    DEATH_FAMILY = "death_family"
    RETIREMENT = "retirement"
    JOB_CHANGE = "job_change"
    HOME_PURCHASE = "home_purchase"
    HOME_SALE = "home_sale"
    INHERITANCE = "inheritance"
    HEALTH_ISSUE = "health_issue"
    BUSINESS_SALE = "business_sale"
    COLLEGE_START = "college_start"
    RELOCATION = "relocation"
    OTHER = "other"


class GoalStatus(Enum):
    """Status of a client financial goal."""
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"
    ACHIEVED = "achieved"
    DEFERRED = "deferred"


class DocumentType(Enum):
    """Compliance and planning documents tracked per client."""
    INVESTMENT_POLICY_STATEMENT = "ips"
    RISK_TOLERANCE_QUESTIONNAIRE = "rtq"
    FINANCIAL_PLAN = "financial_plan"
    ADV_PART_2 = "adv_part_2"          # Annual disclosure delivery
    PRIVACY_NOTICE = "privacy_notice"
    BENEFICIARY_DESIGNATION = "beneficiary_designation"
    TRUST_DOCUMENT = "trust_document"
    ESTATE_PLAN = "estate_plan"
    POWER_OF_ATTORNEY = "power_of_attorney"
    INSURANCE_POLICY = "insurance_policy"
    TAX_RETURN = "tax_return"


class ActionItemStatus(Enum):
    """Status of follow-up items from reviews."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class ActionItemPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class HouseholdMember:
    """An individual within a client household."""
    name: str
    relationship: str          # "primary", "spouse", "child", "parent"
    date_of_birth: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    employer: Optional[str] = None
    occupation: Optional[str] = None
    is_retired: bool = False
    retirement_date: Optional[date] = None
    health_notes: Optional[str] = None  # Relevant for LTC planning
    notes: str = ""

    @property
    def age(self) -> Optional[int]:
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


@dataclass
class Account:
    """An investment account held at the custodian."""
    id: str                        # Custodian account number
    account_type: AccountType
    owner: str                     # Household member name
    custodian: str                 # "Schwab", "Fidelity", etc.
    current_balance: float
    balance_as_of: date
    previous_balance: float = 0.0  # Balance at last review
    previous_balance_date: Optional[date] = None
    inception_date: Optional[date] = None
    is_managed: bool = True        # Managed by the firm vs. held-away
    model_portfolio: Optional[str] = None   # "Growth", "Balanced", etc.
    notes: str = ""

    @property
    def balance_change(self) -> float:
        return self.current_balance - self.previous_balance

    @property
    def balance_change_pct(self) -> float:
        if self.previous_balance == 0:
            return 0.0
        return (self.balance_change / self.previous_balance) * 100


@dataclass
class PerformanceSnapshot:
    """Portfolio performance for a specific period."""
    period_label: str          # "Q4 2025", "YTD 2025", "Since Inception"
    period_start: date
    period_end: date
    portfolio_return_pct: float
    benchmark_return_pct: float
    benchmark_name: str        # "60/40 Blend", "S&P 500", etc.
    net_flows: float           # Contributions minus withdrawals
    beginning_value: float
    ending_value: float

    @property
    def excess_return_pct(self) -> float:
        return self.portfolio_return_pct - self.benchmark_return_pct

    @property
    def growth(self) -> float:
        return self.ending_value - self.beginning_value - self.net_flows


@dataclass
class AssetAllocation:
    """Current asset allocation vs. target."""
    asset_class: str           # "US Equity", "International Equity", "Fixed Income", etc.
    target_pct: float
    actual_pct: float
    market_value: float

    @property
    def drift_pct(self) -> float:
        return self.actual_pct - self.target_pct

    @property
    def needs_rebalance(self) -> bool:
        return abs(self.drift_pct) > 5.0  # 5% threshold


@dataclass
class LifeEvent:
    """A significant life event logged from CRM notes."""
    id: str
    category: LifeEventCategory
    description: str
    event_date: date
    logged_date: date              # When the advisor noted it
    logged_by: str                 # Advisor or staff member
    household_member: Optional[str] = None
    planning_impact: Optional[str] = None  # "May affect retirement timeline"
    follow_up_needed: bool = False
    follow_up_notes: str = ""


@dataclass
class FinancialGoal:
    """A client financial goal tracked in the planning software."""
    id: str
    name: str                      # "Retirement at 62", "College for Sarah"
    category: str                  # "retirement", "education", "estate", "lifestyle"
    target_amount: Optional[float] = None
    target_date: Optional[date] = None
    current_funded_pct: float = 0.0
    status: GoalStatus = GoalStatus.ON_TRACK
    last_reviewed: Optional[date] = None
    notes: str = ""


@dataclass
class ComplianceDocument:
    """A tracked compliance or planning document."""
    document_type: DocumentType
    status: str                    # "current", "expiring", "expired", "missing"
    last_completed: Optional[date] = None
    expiration_date: Optional[date] = None
    renewal_period_months: int = 12
    notes: str = ""

    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.expiration_date:
            return None
        return (self.expiration_date - date.today()).days

    @property
    def is_expiring_soon(self) -> bool:
        days = self.days_until_expiry
        return days is not None and 0 < days <= 60

    @property
    def is_expired(self) -> bool:
        days = self.days_until_expiry
        return days is not None and days <= 0


@dataclass
class ActionItem:
    """A follow-up item from a client review meeting."""
    id: str
    description: str
    assigned_to: str               # Advisor or staff name
    created_date: date
    due_date: Optional[date] = None
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    status: ActionItemStatus = ActionItemStatus.OPEN
    source_meeting: Optional[str] = None   # Meeting date or ID
    completed_date: Optional[date] = None
    notes: str = ""

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status in (ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED):
            return False
        return date.today() > self.due_date

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days


@dataclass
class ReviewRecord:
    """Record of a completed client review meeting."""
    meeting_date: date
    meeting_type: str              # "quarterly_review", "annual_review", "ad_hoc"
    advisor: str
    attendees: list[str]           # Household members who attended
    duration_minutes: int
    topics_discussed: list[str]
    action_items_created: list[str]  # Action item IDs
    notes: str = ""
    client_satisfaction: Optional[int] = None  # 1-5 if surveyed


@dataclass
class Interaction:
    """Any logged interaction with the client (for engagement scoring)."""
    date: date
    interaction_type: str          # "email", "phone", "meeting", "portal_login", "document_signed"
    direction: str                 # "outbound" (we contacted them) or "inbound" (they contacted us)
    initiated_by: str              # Staff member name or "client"
    summary: Optional[str] = None
    response_time_hours: Optional[float] = None  # For emails/calls


# ---------------------------------------------------------------------------
# Client Household (Top-Level Entity)
# ---------------------------------------------------------------------------

@dataclass
class ClientHousehold:
    """A complete client household profile.

    This is the single view that replaces checking 4 systems.
    Everything an advisor needs to know about a client, in one place.
    """
    id: str                        # "HH-001"
    household_name: str            # "The Henderson Household"
    service_tier: ServiceTier
    primary_advisor: str
    secondary_advisor: Optional[str] = None
    client_since: Optional[date] = None
    last_review_date: Optional[date] = None
    next_review_date: Optional[date] = None
    review_frequency: str = "quarterly"   # "quarterly", "semi_annual", "annual"

    # Household composition
    members: list[HouseholdMember] = field(default_factory=list)

    # Financial data
    accounts: list[Account] = field(default_factory=list)
    performance: list[PerformanceSnapshot] = field(default_factory=list)
    asset_allocation: list[AssetAllocation] = field(default_factory=list)
    goals: list[FinancialGoal] = field(default_factory=list)

    # Life events and notes
    life_events: list[LifeEvent] = field(default_factory=list)

    # Compliance
    documents: list[ComplianceDocument] = field(default_factory=list)

    # Action items and interaction history
    action_items: list[ActionItem] = field(default_factory=list)
    review_history: list[ReviewRecord] = field(default_factory=list)
    interactions: list[Interaction] = field(default_factory=list)

    # Risk profile
    risk_tolerance: Optional[str] = None    # "Conservative", "Moderate", "Aggressive"
    investment_objective: Optional[str] = None
    time_horizon: Optional[str] = None

    notes: str = ""

    # -- Computed Properties ------------------------------------------------

    @property
    def total_aum(self) -> float:
        return sum(a.current_balance for a in self.accounts if a.is_managed)

    @property
    def total_aum_previous(self) -> float:
        return sum(a.previous_balance for a in self.accounts if a.is_managed)

    @property
    def aum_change(self) -> float:
        return self.total_aum - self.total_aum_previous

    @property
    def aum_change_pct(self) -> float:
        if self.total_aum_previous == 0:
            return 0.0
        return (self.aum_change / self.total_aum_previous) * 100

    @property
    def managed_accounts(self) -> list[Account]:
        return [a for a in self.accounts if a.is_managed]

    @property
    def held_away_accounts(self) -> list[Account]:
        return [a for a in self.accounts if not a.is_managed]

    @property
    def primary_member(self) -> Optional[HouseholdMember]:
        for m in self.members:
            if m.relationship == "primary":
                return m
        return self.members[0] if self.members else None

    @property
    def spouse(self) -> Optional[HouseholdMember]:
        for m in self.members:
            if m.relationship == "spouse":
                return m
        return None

    # -- Life Events Since Last Review --------------------------------------

    def events_since_last_review(self) -> list[LifeEvent]:
        if not self.last_review_date:
            return self.life_events
        return [
            e for e in self.life_events
            if e.event_date >= self.last_review_date
        ]

    # -- Action Items -------------------------------------------------------

    @property
    def open_action_items(self) -> list[ActionItem]:
        return [
            a for a in self.action_items
            if a.status in (ActionItemStatus.OPEN, ActionItemStatus.IN_PROGRESS)
        ]

    @property
    def overdue_action_items(self) -> list[ActionItem]:
        return [a for a in self.open_action_items if a.is_overdue]

    @property
    def action_item_completion_rate(self) -> float:
        total = len([
            a for a in self.action_items
            if a.status != ActionItemStatus.CANCELLED
        ])
        if total == 0:
            return 100.0
        completed = len([
            a for a in self.action_items
            if a.status == ActionItemStatus.COMPLETED
        ])
        return (completed / total) * 100

    # -- Compliance ---------------------------------------------------------

    @property
    def compliance_issues(self) -> list[ComplianceDocument]:
        return [
            d for d in self.documents
            if d.is_expired or d.is_expiring_soon or d.status == "missing"
        ]

    @property
    def compliance_status(self) -> str:
        issues = self.compliance_issues
        if not issues:
            return "current"
        if any(d.is_expired or d.status == "missing" for d in issues):
            return "action_required"
        return "expiring_soon"

    # -- Review Scheduling --------------------------------------------------

    @property
    def days_until_next_review(self) -> Optional[int]:
        if not self.next_review_date:
            return None
        return (self.next_review_date - date.today()).days

    @property
    def is_review_overdue(self) -> bool:
        days = self.days_until_next_review
        return days is not None and days < 0

    @property
    def review_prep_urgency(self) -> str:
        """How urgently this review needs prep."""
        days = self.days_until_next_review
        if days is None:
            return "unscheduled"
        if days < 0:
            return "overdue"
        if days <= 7:
            return "this_week"
        if days <= 14:
            return "next_week"
        if days <= 30:
            return "this_month"
        return "upcoming"

    # -- Summary ------------------------------------------------------------

    def get_profile_summary(self) -> dict:
        primary = self.primary_member
        return {
            "id": self.id,
            "household_name": self.household_name,
            "primary_contact": primary.name if primary else "Unknown",
            "service_tier": self.service_tier.value,
            "advisor": self.primary_advisor,
            "client_since": self.client_since.isoformat() if self.client_since else None,
            "aum": {
                "current": round(self.total_aum, 2),
                "previous": round(self.total_aum_previous, 2),
                "change": round(self.aum_change, 2),
                "change_pct": round(self.aum_change_pct, 1),
            },
            "accounts": {
                "managed": len(self.managed_accounts),
                "held_away": len(self.held_away_accounts),
                "total_count": len(self.accounts),
            },
            "members": [
                {"name": m.name, "relationship": m.relationship, "age": m.age}
                for m in self.members
            ],
            "review": {
                "last_review": self.last_review_date.isoformat() if self.last_review_date else None,
                "next_review": self.next_review_date.isoformat() if self.next_review_date else None,
                "days_until_next": self.days_until_next_review,
                "urgency": self.review_prep_urgency,
                "frequency": self.review_frequency,
            },
            "life_events_since_review": len(self.events_since_last_review()),
            "action_items": {
                "open": len(self.open_action_items),
                "overdue": len(self.overdue_action_items),
                "completion_rate_pct": round(self.action_item_completion_rate, 1),
            },
            "compliance": {
                "status": self.compliance_status,
                "issues": len(self.compliance_issues),
            },
            "goals": {
                "total": len(self.goals),
                "on_track": len([g for g in self.goals if g.status == GoalStatus.ON_TRACK]),
                "at_risk": len([g for g in self.goals if g.status == GoalStatus.AT_RISK]),
            },
        }


# ---------------------------------------------------------------------------
# Client Book (All Households)
# ---------------------------------------------------------------------------

class ClientBook:
    """The firm's complete client book for an advisor or the whole firm."""

    def __init__(self):
        self._households: dict[str, ClientHousehold] = {}

    def add(self, household: ClientHousehold) -> ClientHousehold:
        self._households[household.id] = household
        return household

    def get(self, household_id: str) -> ClientHousehold:
        if household_id not in self._households:
            raise KeyError(f"Household '{household_id}' not found.")
        return self._households[household_id]

    def list_all(self) -> list[ClientHousehold]:
        return list(self._households.values())

    def list_by_advisor(self, advisor: str) -> list[ClientHousehold]:
        return [h for h in self._households.values() if h.primary_advisor == advisor]

    def list_by_tier(self, tier: ServiceTier) -> list[ClientHousehold]:
        return [h for h in self._households.values() if h.service_tier == tier]

    def list_reviews_due(self, within_days: int = 30) -> list[ClientHousehold]:
        cutoff = date.today() + timedelta(days=within_days)
        return [
            h for h in self._households.values()
            if h.next_review_date and h.next_review_date <= cutoff
        ]

    def list_overdue_reviews(self) -> list[ClientHousehold]:
        return [h for h in self._households.values() if h.is_review_overdue]

    def list_compliance_issues(self) -> list[tuple[ClientHousehold, list[ComplianceDocument]]]:
        results = []
        for h in self._households.values():
            issues = h.compliance_issues
            if issues:
                results.append((h, issues))
        return results

    @property
    def total_aum(self) -> float:
        return sum(h.total_aum for h in self._households.values())

    def get_book_summary(self) -> dict:
        all_households = list(self._households.values())
        return {
            "total_households": len(all_households),
            "total_aum": round(self.total_aum, 2),
            "by_tier": {
                tier.value: len(self.list_by_tier(tier))
                for tier in ServiceTier
            },
            "reviews_due_30d": len(self.list_reviews_due(30)),
            "reviews_overdue": len(self.list_overdue_reviews()),
            "compliance_issues": len(self.list_compliance_issues()),
            "total_open_action_items": sum(
                len(h.open_action_items) for h in all_households
            ),
            "total_overdue_action_items": sum(
                len(h.overdue_action_items) for h in all_households
            ),
        }


# ---------------------------------------------------------------------------
# Usage Example — Build a realistic client household
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    today = date.today()
    book = ClientBook()

    # Build the Henderson Household (Platinum client)
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
            HouseholdMember(
                name="Robert Henderson",
                relationship="primary",
                date_of_birth=date(1962, 8, 14),
                email="robert.henderson@email.com",
                employer="Henderson & Associates",
                occupation="Small business owner",
            ),
            HouseholdMember(
                name="Margaret Henderson",
                relationship="spouse",
                date_of_birth=date(1964, 11, 2),
                email="margaret.henderson@email.com",
                employer=None,
                occupation="Retired teacher",
                is_retired=True,
                retirement_date=date(2025, 9, 1),
            ),
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
            PerformanceSnapshot(
                "Since Last Review", today - timedelta(days=95), today,
                8.3, 7.1, "60/40 Blend", 245000,
                919000, 1240000,
            ),
            PerformanceSnapshot(
                "YTD 2026", date(2026, 1, 1), today,
                4.2, 3.8, "60/40 Blend", 0,
                1190000, 1240000,
            ),
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
                      "Margaret retired from teaching after 28 years. Pension: $3,200/mo. Rolled 403(b) to IRA.",
                      date(2025, 9, 1), date(2025, 9, 5), "Michelle Torres",
                      "Margaret Henderson",
                      "Need to update financial plan for earlier retirement. Review income sources."),
            LifeEvent("LE-002", LifeEventCategory.DEATH_FAMILY,
                      "Robert's mother passed away. Potential inheritance — Robert mentioned estate is in probate.",
                      date(2025, 10, 15), date(2025, 10, 18), "Michelle Torres",
                      "Robert Henderson",
                      "Follow up on inheritance amount and timing. May affect estate plan.",
                      follow_up_needed=True),
        ],
        goals=[
            FinancialGoal("G-001", "Retirement at 65 (Robert)",
                          "retirement", 2500000, date(2027, 8, 14),
                          78.0, GoalStatus.ON_TRACK, today - timedelta(days=95)),
            FinancialGoal("G-002", "College fund for grandson",
                          "education", 120000, date(2036, 9, 1),
                          32.0, GoalStatus.ON_TRACK, today - timedelta(days=95)),
            FinancialGoal("G-003", "Vacation home down payment",
                          "lifestyle", 150000, date(2028, 6, 1),
                          45.0, GoalStatus.AT_RISK, today - timedelta(days=95),
                          notes="May need to re-evaluate timeline given Margaret's retirement"),
        ],
        documents=[
            ComplianceDocument(DocumentType.INVESTMENT_POLICY_STATEMENT,
                               "current", date(2025, 6, 15), date(2026, 6, 15), 12),
            ComplianceDocument(DocumentType.RISK_TOLERANCE_QUESTIONNAIRE,
                               "current", date(2025, 8, 1), date(2026, 4, 1), 12),
            ComplianceDocument(DocumentType.FINANCIAL_PLAN,
                               "expiring", date(2024, 11, 20), date(2025, 11, 20), 12,
                               "Stale — predates Margaret's retirement"),
            ComplianceDocument(DocumentType.ADV_PART_2,
                               "current", date(2026, 1, 15), date(2027, 1, 15), 12),
            ComplianceDocument(DocumentType.BENEFICIARY_DESIGNATION,
                               "current", date(2023, 4, 10), None, 0,
                               "Review — may need update given mother's passing"),
        ],
        action_items=[
            ActionItem("AI-001", "Research long-term care insurance options for both",
                       "Michelle Torres", today - timedelta(days=95),
                       today - timedelta(days=65), ActionItemPriority.MEDIUM,
                       ActionItemStatus.OPEN, "Q3 2025 Review"),
            ActionItem("AI-002", "Rebalance international equity allocation",
                       "Michelle Torres", today - timedelta(days=95),
                       today - timedelta(days=80), ActionItemPriority.LOW,
                       ActionItemStatus.COMPLETED, "Q3 2025 Review",
                       completed_date=today - timedelta(days=78)),
            ActionItem("AI-003", "Update beneficiary designations on rollover IRA",
                       "Sarah Kim", today - timedelta(days=60),
                       today - timedelta(days=30), ActionItemPriority.HIGH,
                       ActionItemStatus.OPEN,
                       notes="Margaret's new rollover IRA needs beneficiary designation"),
        ],
        review_history=[
            ReviewRecord(
                today - timedelta(days=95), "semi_annual_review",
                "Michelle Torres", ["Robert Henderson", "Margaret Henderson"],
                50, ["Portfolio review", "Margaret's retirement planning",
                      "403(b) rollover", "Risk tolerance update"],
                ["AI-001", "AI-002"],
            ),
        ],
        interactions=[
            Interaction(today - timedelta(days=95), "meeting", "outbound", "Michelle Torres", "Semi-annual review"),
            Interaction(today - timedelta(days=60), "email", "inbound", "client", "Question about rollover status", 4.0),
            Interaction(today - timedelta(days=55), "email", "outbound", "Sarah Kim", "Rollover confirmation"),
            Interaction(today - timedelta(days=18), "phone", "inbound", "client", "Robert called about mother's estate"),
            Interaction(today - timedelta(days=5), "email", "outbound", "Michelle Torres", "Review scheduling"),
        ],
    )
    book.add(henderson)

    # Build a second household for contrast (smaller, less engaged)
    chen = ClientHousehold(
        id="HH-002",
        household_name="The Chen Household",
        service_tier=ServiceTier.SILVER,
        primary_advisor="Michelle Torres",
        client_since=date(2021, 11, 1),
        last_review_date=today - timedelta(days=200),
        next_review_date=today - timedelta(days=15),  # Overdue
        review_frequency="annual",
        risk_tolerance="Moderate",
        members=[
            HouseholdMember("David Chen", "primary", date(1978, 3, 22),
                            "dchen@email.com", "TechCorp", "Software engineer"),
        ],
        accounts=[
            Account("ACCT-010", AccountType.INDIVIDUAL, "David Chen",
                    "Schwab", 185000, today, 192000, today - timedelta(days=200)),
            Account("ACCT-011", AccountType.ROTH_IRA, "David Chen",
                    "Schwab", 94000, today, 88000, today - timedelta(days=200)),
        ],
        goals=[
            FinancialGoal("G-010", "Early retirement at 55",
                          "retirement", 1800000, date(2033, 3, 22),
                          22.0, GoalStatus.AT_RISK, today - timedelta(days=200)),
        ],
        documents=[
            ComplianceDocument(DocumentType.INVESTMENT_POLICY_STATEMENT,
                               "expired", date(2024, 5, 10), date(2025, 5, 10), 12),
            ComplianceDocument(DocumentType.RISK_TOLERANCE_QUESTIONNAIRE,
                               "expired", date(2024, 3, 1), date(2025, 3, 1), 12),
        ],
        action_items=[
            ActionItem("AI-010", "Increase 401k contribution to maximize match",
                       "Michelle Torres", today - timedelta(days=200),
                       today - timedelta(days=170), ActionItemPriority.HIGH,
                       ActionItemStatus.OPEN, "Annual Review 2025"),
        ],
        interactions=[
            Interaction(today - timedelta(days=200), "meeting", "outbound", "Michelle Torres", "Annual review"),
            Interaction(today - timedelta(days=120), "email", "outbound", "Michelle Torres", "Check-in email", None),
            Interaction(today - timedelta(days=90), "email", "outbound", "Sarah Kim", "Review scheduling attempt"),
            Interaction(today - timedelta(days=60), "email", "outbound", "Michelle Torres", "Second scheduling attempt"),
        ],
    )
    book.add(chen)

    # Print summaries
    print("=== CLIENT BOOK SUMMARY ===\n")
    bs = book.get_book_summary()
    print(f"Total households: {bs['total_households']}")
    print(f"Total AUM: ${bs['total_aum']:,.0f}")
    print(f"By tier: {bs['by_tier']}")
    print(f"Reviews due (30d): {bs['reviews_due_30d']}")
    print(f"Reviews overdue: {bs['reviews_overdue']}")
    print(f"Open action items: {bs['total_open_action_items']}")
    print(f"Overdue action items: {bs['total_overdue_action_items']}")

    for hh in book.list_all():
        print(f"\n{'=' * 50}")
        s = hh.get_profile_summary()
        print(f"Household: {s['household_name']}")
        print(f"Tier: {s['service_tier']} | Advisor: {s['advisor']}")
        print(f"AUM: ${s['aum']['current']:,.0f} ({s['aum']['change_pct']:+.1f}%)")
        print(f"Next review: {s['review']['next_review']} ({s['review']['urgency']})")
        print(f"Life events since review: {s['life_events_since_review']}")
        print(f"Action items — open: {s['action_items']['open']}, overdue: {s['action_items']['overdue']}")
        print(f"Compliance: {s['compliance']['status']} ({s['compliance']['issues']} issues)")
