"""
Engagement Scorer — Detects early attrition signals before clients leave.

Added after the firm lost 3 clients in Q4 2025 with no warning. In each
case, the pattern was visible in retrospect: fewer logins, skipped
reviews, unanswered emails, declining AUM. Nobody was watching for it
because there was no system to aggregate these signals.

The engagement score is a composite of 6 weighted signals:
1. Meeting attendance (did they show up to their scheduled reviews?)
2. Response time (how quickly do they reply to advisor outreach?)
3. Interaction frequency (how often are we in contact?)
4. AUM trend (is money flowing in or out?)
5. Portal activity (are they logging in and viewing statements?)
6. Document compliance (are they returning signed documents?)

A declining score triggers an alert to the advisor before the client
is already talking to another firm.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional
from collections import defaultdict

from client_profiler import (
    ClientHousehold,
    ClientBook,
    ServiceTier,
    Interaction,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EngagementLevel(Enum):
    """Overall engagement health."""
    STRONG = "strong"          # Score >= 80. Engaged, responsive, growing.
    HEALTHY = "healthy"        # Score 60-79. Normal patterns.
    COOLING = "cooling"        # Score 40-59. Early warning signs.
    AT_RISK = "at_risk"        # Score 20-39. Multiple disengagement signals.
    DISENGAGED = "disengaged"  # Score < 20. Likely already exploring alternatives.


class TrendDirection(Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SignalScore:
    """Individual engagement signal score."""
    signal_name: str
    weight: float              # 0-1, all weights sum to 1
    raw_score: float           # 0-100
    weighted_score: float      # raw_score * weight
    detail: str                # Human-readable explanation
    data_points: int           # Number of data points used


@dataclass
class EngagementReport:
    """Complete engagement assessment for a client household."""
    household_id: str
    household_name: str
    advisor: str
    assessed_at: datetime
    assessment_period_days: int

    # Scores
    composite_score: float           # 0-100 weighted average
    engagement_level: EngagementLevel
    signals: list[SignalScore]

    # Trend
    previous_score: Optional[float]
    trend: TrendDirection
    score_change: float

    # Risk assessment
    attrition_risk: str              # "low", "moderate", "high", "critical"
    risk_factors: list[str]          # Specific reasons for concern
    recommended_actions: list[str]   # What the advisor should do

    # Context
    aum: float
    tenure_years: Optional[int]
    service_tier: str
    last_interaction_days: int
    last_meeting_days: int


@dataclass
class EngagementAlert:
    """Alert when a client's engagement score drops below thresholds."""
    household_id: str
    household_name: str
    advisor: str
    alert_type: str            # "score_decline", "disengaged", "no_contact"
    severity: str              # "warning", "critical"
    current_score: float
    previous_score: Optional[float]
    message: str
    recommended_action: str
    generated_at: datetime


# ---------------------------------------------------------------------------
# Scorer Configuration
# ---------------------------------------------------------------------------

@dataclass
class ScorerConfig:
    """Configurable weights and thresholds for engagement scoring."""
    # Signal weights (must sum to 1.0)
    weight_meeting_attendance: float = 0.20
    weight_response_time: float = 0.20
    weight_interaction_frequency: float = 0.15
    weight_aum_trend: float = 0.20
    weight_portal_activity: float = 0.10
    weight_document_compliance: float = 0.15

    # Assessment window
    assessment_period_days: int = 180    # 6 months of data

    # Thresholds
    cooling_threshold: float = 60.0      # Below this = cooling
    at_risk_threshold: float = 40.0      # Below this = at_risk
    disengaged_threshold: float = 20.0   # Below this = disengaged

    # Alert triggers
    score_decline_alert_pct: float = 15.0  # Alert if score drops > 15% between periods
    no_contact_alert_days: int = 90        # Alert if no interaction in 90 days


# ---------------------------------------------------------------------------
# Engagement Scorer
# ---------------------------------------------------------------------------

class EngagementScorer:
    """Scores client engagement health and detects attrition risk."""

    def __init__(self, config: Optional[ScorerConfig] = None):
        self._config = config or ScorerConfig()
        self._previous_scores: dict[str, float] = {}  # household_id -> last score
        self._alerts: list[EngagementAlert] = []

    def score_client(self, household: ClientHousehold) -> EngagementReport:
        """Generate a complete engagement report for a client household."""
        cfg = self._config
        cutoff = date.today() - timedelta(days=cfg.assessment_period_days)

        # Filter interactions to assessment window
        recent_interactions = [
            i for i in household.interactions
            if i.date >= cutoff
        ]

        # Calculate individual signal scores
        signals = []

        signals.append(self._score_meeting_attendance(household, cutoff))
        signals.append(self._score_response_time(recent_interactions))
        signals.append(self._score_interaction_frequency(recent_interactions, household))
        signals.append(self._score_aum_trend(household))
        signals.append(self._score_portal_activity(recent_interactions))
        signals.append(self._score_document_compliance(household))

        # Composite score
        composite = sum(s.weighted_score for s in signals)
        composite = max(0, min(100, composite))

        # Engagement level
        if composite >= 80:
            level = EngagementLevel.STRONG
        elif composite >= 60:
            level = EngagementLevel.HEALTHY
        elif composite >= 40:
            level = EngagementLevel.COOLING
        elif composite >= 20:
            level = EngagementLevel.AT_RISK
        else:
            level = EngagementLevel.DISENGAGED

        # Trend
        previous = self._previous_scores.get(household.id)
        if previous is not None:
            change = composite - previous
            if change > 5:
                trend = TrendDirection.IMPROVING
            elif change < -5:
                trend = TrendDirection.DECLINING
            else:
                trend = TrendDirection.STABLE
        else:
            change = 0
            trend = TrendDirection.STABLE

        self._previous_scores[household.id] = composite

        # Risk assessment
        risk_factors, actions = self._assess_risk(
            household, signals, composite, level, recent_interactions
        )
        attrition_risk = self._calculate_attrition_risk(composite, trend, risk_factors)

        # Last interaction timing
        last_interaction = max(
            (i.date for i in household.interactions), default=None
        )
        last_meeting = max(
            (i.date for i in household.interactions if i.interaction_type == "meeting"),
            default=None,
        )

        report = EngagementReport(
            household_id=household.id,
            household_name=household.household_name,
            advisor=household.primary_advisor,
            assessed_at=datetime.now(),
            assessment_period_days=cfg.assessment_period_days,
            composite_score=round(composite, 1),
            engagement_level=level,
            signals=signals,
            previous_score=previous,
            trend=trend,
            score_change=round(change, 1),
            attrition_risk=attrition_risk,
            risk_factors=risk_factors,
            recommended_actions=actions,
            aum=household.total_aum,
            tenure_years=(
                (date.today().year - household.client_since.year)
                if household.client_since else None
            ),
            service_tier=household.service_tier.value,
            last_interaction_days=(
                (date.today() - last_interaction).days if last_interaction else 999
            ),
            last_meeting_days=(
                (date.today() - last_meeting).days if last_meeting else 999
            ),
        )

        # Check for alerts
        self._check_alerts(household, report)

        return report

    # -- Signal Scoring Methods ---------------------------------------------

    def _score_meeting_attendance(
        self, hh: ClientHousehold, cutoff: date
    ) -> SignalScore:
        """Score based on whether the client attends scheduled reviews."""
        cfg = self._config

        # Count reviews in the period
        reviews_attended = len([
            r for r in hh.review_history
            if r.meeting_date >= cutoff and len(r.attendees) > 0
        ])

        # Expected reviews based on tier
        expected = {
            ServiceTier.PLATINUM: 2,   # Quarterly = ~2 per 6 months
            ServiceTier.GOLD: 1,       # Semi-annual = 1 per 6 months
            ServiceTier.SILVER: 0.5,   # Annual = 0.5 per 6 months
        }.get(hh.service_tier, 1)

        if expected == 0:
            raw = 80  # Default if no reviews expected
        else:
            attendance_rate = min(reviews_attended / expected, 1.0)
            raw = attendance_rate * 100

        # Bonus for attending with spouse
        if any(r for r in hh.review_history if r.meeting_date >= cutoff and len(r.attendees) > 1):
            raw = min(100, raw + 10)

        weighted = raw * cfg.weight_meeting_attendance

        return SignalScore(
            signal_name="Meeting Attendance",
            weight=cfg.weight_meeting_attendance,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            detail=f"{reviews_attended} of {expected:.0f} expected reviews attended",
            data_points=reviews_attended,
        )

    def _score_response_time(
        self, interactions: list[Interaction]
    ) -> SignalScore:
        """Score based on how quickly the client responds to outreach."""
        cfg = self._config

        # Look at outbound-then-inbound pairs
        inbound = [
            i for i in interactions
            if i.direction == "inbound" and i.response_time_hours is not None
        ]

        if not inbound:
            # No response data — use interaction patterns
            client_initiated = len([i for i in interactions if i.direction == "inbound"])
            raw = min(100, client_initiated * 25)  # Client reaching out is good
            detail = f"{client_initiated} client-initiated contacts (no response time data)"
        else:
            avg_response = sum(i.response_time_hours for i in inbound) / len(inbound)
            if avg_response <= 4:
                raw = 100
            elif avg_response <= 24:
                raw = 80
            elif avg_response <= 72:
                raw = 50
            elif avg_response <= 168:  # 1 week
                raw = 25
            else:
                raw = 10
            detail = f"Average response time: {avg_response:.0f} hours"

        weighted = raw * cfg.weight_response_time

        return SignalScore(
            signal_name="Response Time",
            weight=cfg.weight_response_time,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            detail=detail,
            data_points=len(inbound) if inbound else len(interactions),
        )

    def _score_interaction_frequency(
        self, interactions: list[Interaction], hh: ClientHousehold
    ) -> SignalScore:
        """Score based on how often we're in contact."""
        cfg = self._config

        total = len(interactions)
        inbound = len([i for i in interactions if i.direction == "inbound"])
        outbound = len([i for i in interactions if i.direction == "outbound"])

        # Expected frequency based on tier
        expected_per_6mo = {
            ServiceTier.PLATINUM: 12,  # ~2 per month
            ServiceTier.GOLD: 6,       # ~1 per month
            ServiceTier.SILVER: 3,     # ~1 per 2 months
        }.get(hh.service_tier, 6)

        if expected_per_6mo == 0:
            raw = 50
        else:
            frequency_ratio = min(total / expected_per_6mo, 1.5)
            raw = min(100, frequency_ratio * 70)

        # Bonus for client-initiated contact (shows engagement)
        if total > 0:
            inbound_ratio = inbound / total
            if inbound_ratio > 0.3:
                raw = min(100, raw + 15)

        # Penalty for long gaps
        if interactions:
            sorted_dates = sorted(i.date for i in interactions)
            if len(sorted_dates) > 1:
                gaps = [
                    (sorted_dates[i+1] - sorted_dates[i]).days
                    for i in range(len(sorted_dates) - 1)
                ]
                max_gap = max(gaps)
                if max_gap > 60:
                    raw = max(0, raw - 15)

        weighted = raw * cfg.weight_interaction_frequency

        return SignalScore(
            signal_name="Interaction Frequency",
            weight=cfg.weight_interaction_frequency,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            detail=f"{total} interactions ({inbound} inbound, {outbound} outbound). Expected ~{expected_per_6mo}.",
            data_points=total,
        )

    def _score_aum_trend(self, hh: ClientHousehold) -> SignalScore:
        """Score based on AUM direction — is money flowing in or out?"""
        cfg = self._config

        change_pct = hh.aum_change_pct

        # Separate market performance from net flows
        # Positive change with no flows = market growth (neutral signal)
        # Positive change with inflows = very positive
        # Negative change with outflows = very negative
        net_flows = sum(
            p.net_flows for p in hh.performance
        )

        if net_flows > 0:
            # Client is adding money — very positive signal
            raw = min(100, 70 + (net_flows / hh.total_aum * 100) * 3)
            detail = f"AUM {change_pct:+.1f}% with ${net_flows:,.0f} net inflows"
        elif net_flows < 0:
            # Client is withdrawing — could be planned or concerning
            withdrawal_pct = abs(net_flows) / max(hh.total_aum_previous, 1) * 100
            if withdrawal_pct > 20:
                raw = 15  # Large withdrawal, very concerning
            elif withdrawal_pct > 10:
                raw = 35
            elif withdrawal_pct > 5:
                raw = 50
            else:
                raw = 65  # Small withdrawal, probably planned
            detail = f"AUM {change_pct:+.1f}% with ${abs(net_flows):,.0f} net outflows ({withdrawal_pct:.1f}%)"
        else:
            # No flow data — use AUM change as proxy
            if change_pct > 5:
                raw = 75
            elif change_pct > 0:
                raw = 65
            elif change_pct > -5:
                raw = 50
            else:
                raw = 30
            detail = f"AUM {change_pct:+.1f}% (no flow data)"

        weighted = raw * cfg.weight_aum_trend

        return SignalScore(
            signal_name="AUM Trend",
            weight=cfg.weight_aum_trend,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            detail=detail,
            data_points=len(hh.performance),
        )

    def _score_portal_activity(
        self, interactions: list[Interaction]
    ) -> SignalScore:
        """Score based on client portal logins and document views."""
        cfg = self._config

        portal_logins = len([
            i for i in interactions
            if i.interaction_type == "portal_login"
        ])

        doc_signed = len([
            i for i in interactions
            if i.interaction_type == "document_signed"
        ])

        # Expected: ~1 login per month for an engaged client
        expected_logins = cfg.assessment_period_days / 30

        if portal_logins == 0 and doc_signed == 0:
            raw = 30  # No digital activity, but might prefer phone/email
            detail = "No portal logins or digital activity recorded"
        else:
            login_ratio = min(portal_logins / max(expected_logins, 1), 1.5)
            raw = min(100, login_ratio * 60 + doc_signed * 10)
            detail = f"{portal_logins} portal logins, {doc_signed} documents signed digitally"

        weighted = raw * cfg.weight_portal_activity

        return SignalScore(
            signal_name="Portal Activity",
            weight=cfg.weight_portal_activity,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            detail=detail,
            data_points=portal_logins + doc_signed,
        )

    def _score_document_compliance(
        self, hh: ClientHousehold
    ) -> SignalScore:
        """Score based on whether clients return compliance documents on time."""
        cfg = self._config

        total_docs = len(hh.documents)
        if total_docs == 0:
            return SignalScore(
                "Document Compliance", cfg.weight_document_compliance,
                50, 50 * cfg.weight_document_compliance,
                "No documents tracked", 0,
            )

        current = len([d for d in hh.documents if d.status == "current"])
        expiring = len([d for d in hh.documents if d.is_expiring_soon])
        expired = len([d for d in hh.documents if d.is_expired or d.status == "missing"])

        compliance_rate = current / total_docs
        raw = compliance_rate * 80  # 80% weight for current docs

        if expired > 0:
            raw = max(0, raw - expired * 15)

        if expiring > 0:
            raw = max(0, raw - expiring * 5)

        weighted = raw * cfg.weight_document_compliance

        return SignalScore(
            signal_name="Document Compliance",
            weight=cfg.weight_document_compliance,
            raw_score=round(raw, 1),
            weighted_score=round(weighted, 1),
            detail=f"{current}/{total_docs} current, {expiring} expiring, {expired} expired/missing",
            data_points=total_docs,
        )

    # -- Risk Assessment ----------------------------------------------------

    def _assess_risk(
        self,
        hh: ClientHousehold,
        signals: list[SignalScore],
        score: float,
        level: EngagementLevel,
        interactions: list[Interaction],
    ) -> tuple[list[str], list[str]]:
        """Identify specific risk factors and recommended actions."""
        risk_factors = []
        actions = []

        # Check each signal for concerning scores
        for signal in signals:
            if signal.raw_score < 30:
                risk_factors.append(f"Low {signal.signal_name.lower()} ({signal.raw_score:.0f}/100)")

        # No recent interaction
        last = max((i.date for i in hh.interactions), default=None)
        if last:
            days_since = (date.today() - last).days
            if days_since > 90:
                risk_factors.append(f"No contact in {days_since} days")
                actions.append("Schedule a personal check-in call this week.")
            elif days_since > 60:
                risk_factors.append(f"Last contact was {days_since} days ago")
                actions.append("Send a personal email or schedule a brief call.")

        # Outbound-heavy interactions (we're chasing them)
        outbound = len([i for i in interactions if i.direction == "outbound"])
        inbound = len([i for i in interactions if i.direction == "inbound"])
        if outbound > 0 and inbound == 0:
            risk_factors.append("All interactions are firm-initiated (client never reaches out)")
            actions.append("Try a different communication channel or ask if they prefer less frequent contact.")
        elif outbound > inbound * 3 and outbound > 3:
            risk_factors.append(f"Heavily outbound interaction pattern ({outbound} out vs {inbound} in)")

        # Skipped reviews
        if hh.is_review_overdue:
            risk_factors.append("Scheduled review is overdue")
            actions.append("Priority: reschedule the overdue review immediately.")

        # AUM decline
        if hh.aum_change_pct < -10:
            risk_factors.append(f"AUM declined {hh.aum_change_pct:.1f}% since last review")
            actions.append("Investigate whether outflows are planned distributions or a retention issue.")

        # Open action items signaling neglect
        overdue_items = hh.overdue_action_items
        if len(overdue_items) >= 2:
            risk_factors.append(f"{len(overdue_items)} overdue action items (client may feel neglected)")
            actions.append("Clear overdue action items before next meeting.")

        # General recommendations based on level
        if level in (EngagementLevel.COOLING, EngagementLevel.AT_RISK):
            if not actions:
                actions.append("Schedule a touchpoint outside the normal review cycle.")
                actions.append("Consider whether service tier or advisor assignment needs adjustment.")

        if level == EngagementLevel.DISENGAGED:
            actions.insert(0, "URGENT: Senior advisor or principal should personally reach out.")
            actions.append("Prepare for potential retention conversation.")

        return risk_factors, actions

    def _calculate_attrition_risk(
        self,
        score: float,
        trend: TrendDirection,
        risk_factors: list[str],
    ) -> str:
        """Calculate overall attrition risk level."""
        if score < 20:
            return "critical"
        if score < 40 or (score < 60 and trend == TrendDirection.DECLINING):
            return "high"
        if score < 60 or len(risk_factors) >= 3:
            return "moderate"
        return "low"

    # -- Alerts -------------------------------------------------------------

    def _check_alerts(
        self, hh: ClientHousehold, report: EngagementReport
    ) -> None:
        """Generate alerts for concerning engagement patterns."""
        cfg = self._config

        # Score decline alert
        if report.previous_score is not None:
            decline_pct = (
                (report.previous_score - report.composite_score)
                / max(report.previous_score, 1) * 100
            )
            if decline_pct >= cfg.score_decline_alert_pct:
                self._alerts.append(EngagementAlert(
                    household_id=hh.id,
                    household_name=hh.household_name,
                    advisor=hh.primary_advisor,
                    alert_type="score_decline",
                    severity="critical" if decline_pct > 25 else "warning",
                    current_score=report.composite_score,
                    previous_score=report.previous_score,
                    message=(
                        f"Engagement score dropped {decline_pct:.0f}% "
                        f"({report.previous_score:.0f} -> {report.composite_score:.0f})"
                    ),
                    recommended_action=report.recommended_actions[0] if report.recommended_actions else "Review client engagement.",
                    generated_at=datetime.now(),
                ))

        # No contact alert
        if report.last_interaction_days >= cfg.no_contact_alert_days:
            self._alerts.append(EngagementAlert(
                household_id=hh.id,
                household_name=hh.household_name,
                advisor=hh.primary_advisor,
                alert_type="no_contact",
                severity="warning",
                current_score=report.composite_score,
                previous_score=report.previous_score,
                message=f"No interaction in {report.last_interaction_days} days",
                recommended_action="Schedule a personal check-in call.",
                generated_at=datetime.now(),
            ))

        # Disengaged alert
        if report.engagement_level == EngagementLevel.DISENGAGED:
            self._alerts.append(EngagementAlert(
                household_id=hh.id,
                household_name=hh.household_name,
                advisor=hh.primary_advisor,
                alert_type="disengaged",
                severity="critical",
                current_score=report.composite_score,
                previous_score=report.previous_score,
                message="Client is disengaged. Multiple attrition signals detected.",
                recommended_action="URGENT: Senior advisor personal outreach required.",
                generated_at=datetime.now(),
            ))

    def get_alerts(self, advisor: Optional[str] = None) -> list[EngagementAlert]:
        alerts = self._alerts
        if advisor:
            alerts = [a for a in alerts if a.advisor == advisor]
        return alerts

    # -- Batch Scoring ------------------------------------------------------

    def score_book(self, book: ClientBook) -> list[EngagementReport]:
        """Score all clients in the book."""
        reports = []
        for hh in book.list_all():
            report = self.score_client(hh)
            reports.append(report)
        reports.sort(key=lambda r: r.composite_score)
        return reports

    def get_book_summary(self, reports: list[EngagementReport]) -> dict:
        """Firm-wide engagement summary."""
        by_level = defaultdict(int)
        by_risk = defaultdict(int)
        for r in reports:
            by_level[r.engagement_level.value] += 1
            by_risk[r.attrition_risk] += 1

        return {
            "total_clients": len(reports),
            "average_score": round(
                sum(r.composite_score for r in reports) / max(len(reports), 1), 1
            ),
            "by_engagement_level": dict(by_level),
            "by_attrition_risk": dict(by_risk),
            "at_risk_clients": [
                {
                    "household": r.household_name,
                    "score": r.composite_score,
                    "level": r.engagement_level.value,
                    "risk": r.attrition_risk,
                    "aum": r.aum,
                    "risk_factors": r.risk_factors[:3],
                }
                for r in reports
                if r.attrition_risk in ("high", "critical")
            ],
            "total_aum_at_risk": round(
                sum(r.aum for r in reports if r.attrition_risk in ("high", "critical")), 2
            ),
            "total_alerts": len(self._alerts),
        }


# ---------------------------------------------------------------------------
# Usage Example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from client_profiler import (
        ClientHousehold, ClientBook, ServiceTier, HouseholdMember, Account,
        AccountType, PerformanceSnapshot, ComplianceDocument, DocumentType,
        ReviewRecord, Interaction,
    )

    today = date.today()
    book = ClientBook()

    # Henderson — engaged client
    henderson = ClientHousehold(
        id="HH-001",
        household_name="The Henderson Household",
        service_tier=ServiceTier.GOLD,
        primary_advisor="Michelle Torres",
        client_since=date(2017, 3, 15),
        last_review_date=today - timedelta(days=95),
        next_review_date=today + timedelta(days=12),
        members=[
            HouseholdMember("Robert Henderson", "primary", date(1962, 8, 14)),
            HouseholdMember("Margaret Henderson", "spouse", date(1964, 11, 2)),
        ],
        accounts=[
            Account("A1", AccountType.JOINT, "Robert & Margaret", "Schwab",
                    1240000, today, 919000, today - timedelta(days=95)),
        ],
        performance=[
            PerformanceSnapshot("6mo", today - timedelta(days=180), today,
                                8.3, 7.1, "60/40", 245000, 919000, 1240000),
        ],
        documents=[
            ComplianceDocument(DocumentType.INVESTMENT_POLICY_STATEMENT,
                               "current", date(2025, 6, 15), date(2026, 6, 15)),
            ComplianceDocument(DocumentType.RISK_TOLERANCE_QUESTIONNAIRE,
                               "current", date(2025, 8, 1), date(2026, 4, 1)),
            ComplianceDocument(DocumentType.FINANCIAL_PLAN,
                               "expiring", date(2024, 11, 20), date(2025, 11, 20)),
            ComplianceDocument(DocumentType.ADV_PART_2,
                               "current", date(2026, 1, 15), date(2027, 1, 15)),
        ],
        review_history=[
            ReviewRecord(today - timedelta(days=95), "semi_annual_review",
                         "Michelle Torres", ["Robert Henderson", "Margaret Henderson"],
                         50, ["Portfolio", "Retirement"], []),
        ],
        interactions=[
            Interaction(today - timedelta(days=95), "meeting", "outbound", "Michelle Torres"),
            Interaction(today - timedelta(days=60), "email", "inbound", "client", response_time_hours=4.0),
            Interaction(today - timedelta(days=55), "email", "outbound", "Sarah Kim"),
            Interaction(today - timedelta(days=18), "phone", "inbound", "client"),
            Interaction(today - timedelta(days=5), "email", "outbound", "Michelle Torres"),
        ],
    )
    book.add(henderson)

    # Chen — disengaging client
    chen = ClientHousehold(
        id="HH-002",
        household_name="The Chen Household",
        service_tier=ServiceTier.SILVER,
        primary_advisor="Michelle Torres",
        client_since=date(2021, 11, 1),
        last_review_date=today - timedelta(days=200),
        next_review_date=today - timedelta(days=15),
        members=[
            HouseholdMember("David Chen", "primary", date(1978, 3, 22)),
        ],
        accounts=[
            Account("A10", AccountType.INDIVIDUAL, "David Chen", "Schwab",
                    279000, today, 310000, today - timedelta(days=200)),
        ],
        performance=[
            PerformanceSnapshot("6mo", today - timedelta(days=180), today,
                                -2.1, 3.8, "60/40", -35000, 310000, 279000),
        ],
        documents=[
            ComplianceDocument(DocumentType.INVESTMENT_POLICY_STATEMENT,
                               "expired", date(2024, 5, 10), date(2025, 5, 10)),
            ComplianceDocument(DocumentType.RISK_TOLERANCE_QUESTIONNAIRE,
                               "expired", date(2024, 3, 1), date(2025, 3, 1)),
        ],
        review_history=[],  # No reviews attended in assessment period
        interactions=[
            Interaction(today - timedelta(days=200), "meeting", "outbound", "Michelle Torres"),
            Interaction(today - timedelta(days=120), "email", "outbound", "Michelle Torres"),
            Interaction(today - timedelta(days=90), "email", "outbound", "Sarah Kim"),
            Interaction(today - timedelta(days=60), "email", "outbound", "Michelle Torres"),
            # No inbound interactions — client is not responding
        ],
    )
    book.add(chen)

    # Score both clients
    scorer = EngagementScorer()
    reports = scorer.score_book(book)

    for report in reports:
        print(f"\n{'=' * 60}")
        print(f"ENGAGEMENT REPORT: {report.household_name}")
        print(f"{'=' * 60}")
        print(f"Score: {report.composite_score}/100 ({report.engagement_level.value.upper()})")
        print(f"Trend: {report.trend.value} | Attrition risk: {report.attrition_risk.upper()}")
        print(f"AUM: ${report.aum:,.0f} | Tenure: {report.tenure_years} years")
        print(f"Last contact: {report.last_interaction_days} days ago | Last meeting: {report.last_meeting_days} days ago")

        print(f"\nSignal Breakdown:")
        for s in report.signals:
            bar = "█" * int(s.raw_score / 10)
            print(f"  {s.signal_name:<25} {s.raw_score:>5.1f}/100 {bar}")
            print(f"  {'':25} {s.detail}")

        if report.risk_factors:
            print(f"\nRisk Factors:")
            for rf in report.risk_factors:
                print(f"  - {rf}")

        if report.recommended_actions:
            print(f"\nRecommended Actions:")
            for ra in report.recommended_actions:
                print(f"  -> {ra}")

    # Alerts
    alerts = scorer.get_alerts()
    if alerts:
        print(f"\n{'=' * 60}")
        print(f"ENGAGEMENT ALERTS ({len(alerts)})")
        print(f"{'=' * 60}")
        for alert in alerts:
            icon = "🔴" if alert.severity == "critical" else "⚠️"
            print(f"\n  {icon} [{alert.severity.upper()}] {alert.household_name}")
            print(f"     {alert.message}")
            print(f"     Action: {alert.recommended_action}")

    # Book summary
    summary = scorer.get_book_summary(reports)
    print(f"\n{'=' * 60}")
    print(f"FIRM-WIDE ENGAGEMENT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Clients: {summary['total_clients']} | Avg score: {summary['average_score']}")
    print(f"By level: {summary['by_engagement_level']}")
    print(f"By risk: {summary['by_attrition_risk']}")
    print(f"AUM at risk: ${summary['total_aum_at_risk']:,.0f}")
