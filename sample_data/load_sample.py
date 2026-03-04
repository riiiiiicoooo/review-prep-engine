"""
Load Sample Data — Imports all sample CSV files and generates a complete briefing.

This script demonstrates the full pipeline:
1. Import portfolio data from custodian CSV
2. Import contacts and interactions from CRM
3. Import goals and plan metadata from planning software
4. Build household profiles
5. Assemble review briefings
6. Score engagement
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.client_profiler import (
    ClientHousehold,
    ClientBook,
    ServiceTier,
    ActionItem,
    ActionItemStatus,
    ActionItemPriority,
    ReviewRecord,
    AssetAllocation,
    PerformanceSnapshot,
)
from src.review_assembler import ReviewAssembler
from src.engagement_scorer import EngagementScorer

from importers.custodial_import import CustodialImporter, SchwabPositionConfig
from importers.crm_import import CRMImporter
from importers.planning_import import PlanningImporter


def load_sample_data() -> ClientBook:
    """Load all sample CSV data and build client households."""

    sample_dir = Path(__file__).parent
    today = date.today()

    # Initialize importers
    custodial = CustodialImporter()
    crm = CRMImporter()
    planning = PlanningImporter()

    # Load CSV files
    print("Loading portfolio data from custodian CSV...")
    accounts = custodial.import_positions(str(sample_dir / "schwab_positions.csv"))
    print(f"  Imported {len(accounts)} accounts")

    print("Loading transactions...")
    transactions = custodial.import_transactions(str(sample_dir / "schwab_transactions.csv"))
    print(f"  Imported {len(transactions)} transactions")

    print("Loading CRM contacts...")
    contacts = crm.import_contacts(str(sample_dir / "crm_contacts.csv"))
    print(f"  Imported {len(contacts)} contacts")

    print("Loading CRM interactions...")
    interactions = crm.import_interactions(str(sample_dir / "crm_interactions.csv"))
    print(f"  Imported {len(interactions)} interactions")

    print("Loading financial goals...")
    goals = planning.import_goals(str(sample_dir / "planning_summary.csv"))
    print(f"  Imported {len(goals)} goals")

    # Build households from contacts and accounts
    book = ClientBook()

    # Henderson Household (GOLD tier)
    henderson_accounts = [a for a in accounts if a.id in ("ACCT-001", "ACCT-002", "ACCT-003", "ACCT-004")]
    henderson_contacts = [c for c in contacts if c.name in ("Robert Henderson", "Margaret Henderson")]
    henderson_goals = [g for g in goals if "Robert" in g.name or "Margaret" in g.name or "grandson" in g.name or "Vacation" in g.name]
    henderson_interactions = [i for i in interactions if "Henderson" in i.summary or "Robert" in i.summary or "Margaret" in i.summary][:5]

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
        members=henderson_contacts,
        accounts=henderson_accounts,
        goals=henderson_goals,
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
        action_items=[
            ActionItem("AI-001", "Research long-term care insurance options for both",
                       "Michelle Torres", today - timedelta(days=95),
                       today - timedelta(days=65), ActionItemPriority.MEDIUM,
                       ActionItemStatus.OPEN, "Q3 2025 Review"),
            ActionItem("AI-003", "Update beneficiary designations on rollover IRA",
                       "Sarah Kim", today - timedelta(days=60),
                       today - timedelta(days=30), ActionItemPriority.HIGH,
                       ActionItemStatus.OPEN),
        ],
        interactions=henderson_interactions,
    )
    book.add(henderson)

    # Williams Household (PLATINUM tier)
    williams_accounts = [a for a in accounts if a.id in ("ACCT-005", "ACCT-006", "ACCT-007")]
    williams_contacts = [c for c in contacts if c.name in ("James Williams", "Susan Williams")]
    williams_goals = [g for g in goals if "James" in g.name or "Susan" in g.name or "Philanthropy" in g.name]

    williams = ClientHousehold(
        id="HH-002",
        household_name="The Williams Household",
        service_tier=ServiceTier.PLATINUM,
        primary_advisor="David Park",
        client_since=date(2015, 6, 1),
        last_review_date=today - timedelta(days=70),
        next_review_date=today + timedelta(days=5),
        review_frequency="quarterly",
        risk_tolerance="Moderate Growth",
        investment_objective="Growth with tax efficiency",
        time_horizon="20+ years",
        members=williams_contacts,
        accounts=williams_accounts,
        goals=williams_goals,
        performance=[
            PerformanceSnapshot(
                "Since Last Review", today - timedelta(days=70), today,
                6.8, 6.2, "60/40 Blend", 125000,
                1125000, 1235000,
            ),
        ],
        asset_allocation=[
            AssetAllocation("US Equity", 40.0, 41.5, 512000),
            AssetAllocation("International Equity", 20.0, 19.2, 237000),
            AssetAllocation("Fixed Income", 30.0, 28.5, 351000),
            AssetAllocation("Alternatives", 10.0, 10.8, 133000),
        ],
        action_items=[
            ActionItem("AI-010", "Review charitable giving strategy for foundation",
                       "David Park", today - timedelta(days=70),
                       today - timedelta(days=40), ActionItemPriority.MEDIUM,
                       ActionItemStatus.OPEN, "Q4 2025 Review"),
        ],
    )
    book.add(williams)

    # Kim Household (PLATINUM tier)
    kim_accounts = [a for a in accounts if a.id in ("ACCT-008", "ACCT-009")]
    kim_contacts = [c for c in contacts if c.name in ("David Kim", "Patricia Kim")]
    kim_goals = [g for g in goals if "David" in g.name or "Patricia" in g.name or "Roth" in g.name]

    kim = ClientHousehold(
        id="HH-003",
        household_name="The Kim Household",
        service_tier=ServiceTier.PLATINUM,
        primary_advisor="Michelle Torres",
        client_since=date(2016, 9, 15),
        last_review_date=today - timedelta(days=100),
        next_review_date=today + timedelta(days=20),
        review_frequency="quarterly",
        risk_tolerance="Aggressive Growth",
        investment_objective="Growth",
        time_horizon="20+ years",
        members=kim_contacts,
        accounts=kim_accounts,
        goals=kim_goals,
        performance=[
            PerformanceSnapshot(
                "Since Last Review", today - timedelta(days=100), today,
                9.5, 7.1, "60/40 Blend", 85000,
                1050000, 1037000,
            ),
        ],
        asset_allocation=[
            AssetAllocation("US Equity", 50.0, 52.1, 540000),
            AssetAllocation("International Equity", 25.0, 24.8, 257000),
            AssetAllocation("Fixed Income", 15.0, 14.2, 147000),
            AssetAllocation("Alternatives", 10.0, 8.9, 92000),
        ],
    )
    book.add(kim)

    # Chen Household (SILVER tier, disengaging)
    chen_accounts = [a for a in accounts if a.id in ("ACCT-010", "ACCT-011")]
    chen_contacts = [c for c in contacts if c.name == "David Chen"]
    chen_goals = [g for g in goals if "David Chen" in g.name]

    chen = ClientHousehold(
        id="HH-004",
        household_name="The Chen Household",
        service_tier=ServiceTier.SILVER,
        primary_advisor="Michelle Torres",
        client_since=date(2021, 11, 1),
        last_review_date=today - timedelta(days=200),
        next_review_date=today - timedelta(days=15),  # Overdue
        review_frequency="annual",
        risk_tolerance="Moderate",
        investment_objective="Growth",
        time_horizon="8-12 years",
        members=chen_contacts,
        accounts=chen_accounts,
        goals=chen_goals,
        performance=[
            PerformanceSnapshot(
                "Since Last Review", today - timedelta(days=200), today,
                -2.1, 3.8, "60/40 Blend", -35000,
                310000, 279000,
            ),
        ],
        asset_allocation=[
            AssetAllocation("US Equity", 60.0, 62.5, 174000),
            AssetAllocation("International Equity", 20.0, 18.3, 51000),
            AssetAllocation("Fixed Income", 15.0, 15.2, 42000),
            AssetAllocation("Cash", 5.0, 4.0, 12000),
        ],
        action_items=[
            ActionItem("AI-020", "Increase 401k contribution to maximize match",
                       "Michelle Torres", today - timedelta(days=200),
                       today - timedelta(days=170), ActionItemPriority.HIGH,
                       ActionItemStatus.OPEN, "Annual Review 2025"),
        ],
    )
    book.add(chen)

    # Thompson Household (GOLD tier, education focus)
    thompson_accounts = [a for a in accounts if a.id in ("ACCT-012", "ACCT-013")]
    thompson_contacts = [c for c in contacts if c.name in ("James Thompson", "Jennifer Thompson", "Michael Thompson")]
    thompson_goals = [g for g in goals if "Michael" in g.name or "College" in g.name]

    thompson = ClientHousehold(
        id="HH-005",
        household_name="The Thompson Household",
        service_tier=ServiceTier.GOLD,
        primary_advisor="David Park",
        client_since=date(2019, 2, 1),
        last_review_date=today - timedelta(days=120),
        next_review_date=today + timedelta(days=8),
        review_frequency="semi_annual",
        risk_tolerance="Moderate Growth",
        investment_objective="Education funding & retirement",
        time_horizon="10-25 years",
        members=thompson_contacts,
        accounts=thompson_accounts,
        goals=thompson_goals,
        performance=[
            PerformanceSnapshot(
                "Since Last Review", today - timedelta(days=120), today,
                5.8, 5.2, "60/40 Blend", 15000,
                228000, 243000,
            ),
        ],
        asset_allocation=[
            AssetAllocation("US Equity", 50.0, 49.2, 119000),
            AssetAllocation("International Equity", 15.0, 15.8, 38000),
            AssetAllocation("Fixed Income", 25.0, 26.0, 63000),
            AssetAllocation("Cash", 10.0, 9.0, 23000),
        ],
        action_items=[
            ActionItem("AI-030", "Review 529 withdrawal strategy for Michael's final year",
                       "David Park", today - timedelta(days=60),
                       today + timedelta(days=30), ActionItemPriority.MEDIUM,
                       ActionItemStatus.IN_PROGRESS, "H2 2025 Review"),
        ],
    )
    book.add(thompson)

    # Johnson Household (PLATINUM tier, physician)
    johnson_accounts = [a for a in accounts if a.id in ("ACCT-014", "ACCT-015")]
    johnson_contacts = [c for c in contacts if c.name in ("Angela Johnson", "Mark Johnson")]
    johnson_goals = [g for g in goals if "Angela" in g.name or "Mark" in g.name or "Physician" in g.name]

    johnson = ClientHousehold(
        id="HH-006",
        household_name="The Johnson Household",
        service_tier=ServiceTier.PLATINUM,
        primary_advisor="David Park",
        client_since=date(2014, 5, 15),
        last_review_date=today - timedelta(days=85),
        next_review_date=today + timedelta(days=18),
        review_frequency="quarterly",
        risk_tolerance="Conservative Growth",
        investment_objective="Retirement & legacy planning",
        time_horizon="10-15 years",
        members=johnson_contacts,
        accounts=johnson_accounts,
        goals=johnson_goals,
        performance=[
            PerformanceSnapshot(
                "Since Last Review", today - timedelta(days=85), today,
                6.2, 5.8, "60/40 Blend", 45000,
                1076000, 1121000,
            ),
        ],
        asset_allocation=[
            AssetAllocation("US Equity", 35.0, 36.8, 412000),
            AssetAllocation("International Equity", 15.0, 14.5, 162000),
            AssetAllocation("Fixed Income", 40.0, 40.2, 451000),
            AssetAllocation("Alternatives", 10.0, 8.5, 95000),
        ],
    )
    book.add(johnson)

    return book


def main():
    """Load sample data and generate briefings."""
    print("\n" + "="*70)
    print("REVIEW PREP ENGINE — SAMPLE DATA LOADER")
    print("="*70 + "\n")

    # Load sample data
    book = load_sample_data()

    # Print book summary
    print("\n" + "="*70)
    print("CLIENT BOOK SUMMARY")
    print("="*70)
    summary = book.get_book_summary()
    print(f"Total households: {summary['total_households']}")
    print(f"Total AUM: ${summary['total_aum']:,.0f}")
    print(f"By tier: {summary['by_tier']}")
    print(f"Reviews due (30d): {summary['reviews_due_30d']}")
    print(f"Reviews overdue: {summary['reviews_overdue']}")
    print(f"Open action items: {summary['total_open_action_items']}")
    print(f"Overdue action items: {summary['total_overdue_action_items']}")

    # Assemble briefings for upcoming reviews
    print("\n" + "="*70)
    print("ASSEMBLING BRIEFINGS FOR UPCOMING REVIEWS")
    print("="*70 + "\n")

    assembler = ReviewAssembler()
    briefings = assembler.assemble_upcoming(book, within_days=30)

    dashboard = assembler.get_prep_dashboard(briefings)
    print(f"Upcoming reviews: {dashboard['total_upcoming']}")
    print(f"High-priority flags: {dashboard['total_high_flags']}")
    print(f"Medium-priority flags: {dashboard['total_medium_flags']}")
    print("\nBriefing status:")
    for briefing_summary in dashboard["briefings"]:
        print(f"  {briefing_summary['household']:<40} {briefing_summary['meeting_date']} [{briefing_summary['tier']:<10}] "
              f"High: {briefing_summary['high_flags']} | Medium: {briefing_summary['medium_flags']}")

    # Score engagement
    print("\n" + "="*70)
    print("ENGAGEMENT SCORING")
    print("="*70 + "\n")

    scorer = EngagementScorer()
    reports = scorer.score_book(book)

    print("Client engagement scores:")
    for report in sorted(reports, key=lambda r: r.composite_score, reverse=True):
        print(f"  {report.household_name:<40} {report.composite_score:>5.1f}/100 [{report.engagement_level.value:<12}] AUM: ${report.aum:>12,.0f}")

    book_summary = scorer.get_book_summary(reports)
    print(f"\nAverage engagement score: {book_summary['average_score']}")
    print(f"Engagement levels: {book_summary['by_engagement_level']}")
    print(f"Attrition risk: {book_summary['by_attrition_risk']}")
    print(f"Total AUM at risk: ${book_summary['total_aum_at_risk']:,.0f}")

    if book_summary['at_risk_clients']:
        print(f"\nClients at high/critical risk ({len(book_summary['at_risk_clients'])}):")
        for client in book_summary['at_risk_clients']:
            print(f"  {client['household']:<40} Score: {client['score']:>5.1f} | Risk: {client['risk']:<10} | AUM: ${client['aum']:>12,.0f}")

    print("\n" + "="*70)
    print("SAMPLE DATA LOAD COMPLETE")
    print("="*70 + "\n")

    return book, briefings, reports


if __name__ == "__main__":
    main()
