"""
Planning Importer — Reads MoneyGuidePro/eMoney planning summary export CSV files.

Maps financial plan data into FinancialGoal and ComplianceDocument objects.
"""

import csv
from datetime import date, datetime
from typing import Optional, List, Dict

from src.client_profiler import (
    FinancialGoal,
    GoalStatus,
    ComplianceDocument,
    DocumentType,
)


class PlanningImporter:
    """Imports financial plan data from planning software CSV exports."""

    GOAL_STATUS_MAP = {
        "On Track": GoalStatus.ON_TRACK,
        "At Risk": GoalStatus.AT_RISK,
        "Off Track": GoalStatus.OFF_TRACK,
        "Achieved": GoalStatus.ACHIEVED,
        "Deferred": GoalStatus.DEFERRED,
    }

    GOAL_CATEGORY_MAP = {
        "retirement": "retirement",
        "education": "education",
        "college": "education",
        "estate": "estate",
        "legacy": "estate",
        "lifestyle": "lifestyle",
        "vacation": "lifestyle",
        "home": "lifestyle",
    }

    def __init__(self):
        self._goals: List[FinancialGoal] = []
        self._plan_documents: List[ComplianceDocument] = []

    def import_goals(
        self,
        csv_file: str,
    ) -> List[FinancialGoal]:
        """Import financial goals from planning software CSV.

        Expected columns:
        - GoalName
        - GoalCategory (retirement, education, estate, lifestyle)
        - TargetAmount (optional)
        - TargetDate (YYYY-MM-DD)
        - FundedPercent (0-100)
        - Status (On Track, At Risk, Off Track, Achieved, Deferred)
        - LastReviewDate (YYYY-MM-DD, optional)
        - Notes
        """
        goals = []
        goal_id_counter = 1

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    goal_name = row.get("GoalName", "").strip()
                    if not goal_name:
                        continue

                    category_str = row.get("GoalCategory", "lifestyle").strip().lower()
                    category = self.GOAL_CATEGORY_MAP.get(category_str, "lifestyle")

                    target_amount_str = row.get("TargetAmount", "").replace("$", "").replace(",", "").strip()
                    try:
                        target_amount = float(target_amount_str) if target_amount_str else None
                    except ValueError:
                        target_amount = None

                    target_date_str = row.get("TargetDate", "").strip()
                    try:
                        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date() if target_date_str else None
                    except (ValueError, TypeError):
                        target_date = None

                    funded_str = row.get("FundedPercent", "0").strip("%")
                    try:
                        funded_pct = float(funded_str)
                    except ValueError:
                        funded_pct = 0.0

                    status_str = row.get("Status", "On Track").strip()
                    status = self.GOAL_STATUS_MAP.get(status_str, GoalStatus.ON_TRACK)

                    last_reviewed_str = row.get("LastReviewDate", "").strip()
                    try:
                        last_reviewed = datetime.strptime(last_reviewed_str, "%Y-%m-%d").date() if last_reviewed_str else None
                    except (ValueError, TypeError):
                        last_reviewed = None

                    goal = FinancialGoal(
                        id=f"G-{goal_id_counter:03d}",
                        name=goal_name,
                        category=category,
                        target_amount=target_amount,
                        target_date=target_date,
                        current_funded_pct=funded_pct,
                        status=status,
                        last_reviewed=last_reviewed,
                        notes=row.get("Notes", "").strip(),
                    )
                    goals.append(goal)
                    goal_id_counter += 1

                except Exception as e:
                    print(f"Warning: Skipping goal row: {e}")
                    continue

        self._goals.extend(goals)
        return goals

    def import_plan_metadata(
        self,
        csv_file: str,
    ) -> List[ComplianceDocument]:
        """Import plan creation and review dates as compliance documents.

        Expected columns:
        - PlanName
        - CreatedDate (YYYY-MM-DD)
        - LastReviewDate (YYYY-MM-DD)
        - NextReviewDate (YYYY-MM-DD)
        - Status (current, expiring, expired, missing)
        - Notes
        """
        documents = []

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    plan_name = row.get("PlanName", "Financial Plan").strip()

                    created_str = row.get("CreatedDate", "").strip()
                    try:
                        created_date = datetime.strptime(created_str, "%Y-%m-%d").date() if created_str else None
                    except (ValueError, TypeError):
                        created_date = None

                    next_review_str = row.get("NextReviewDate", "").strip()
                    try:
                        next_review_date = datetime.strptime(next_review_str, "%Y-%m-%d").date() if next_review_str else None
                    except (ValueError, TypeError):
                        next_review_date = None

                    status = row.get("Status", "current").strip().lower()
                    notes = row.get("Notes", "").strip()

                    doc = ComplianceDocument(
                        document_type=DocumentType.FINANCIAL_PLAN,
                        status=status,
                        last_completed=created_date,
                        expiration_date=next_review_date,
                        renewal_period_months=12,
                        notes=notes or f"Plan created: {plan_name}",
                    )
                    documents.append(doc)

                except Exception as e:
                    print(f"Warning: Skipping plan metadata row: {e}")
                    continue

        self._plan_documents.extend(documents)
        return documents

    def import_projections(
        self,
        csv_file: str,
    ) -> List[Dict]:
        """Import projection data for scenario analysis.

        Expected columns:
        - ScenarioName
        - Year
        - Age
        - ProjectedBalance
        - ProjectedIncome
        - WithdrawalAmount
        - Notes
        """
        projections = []

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    scenario_name = row.get("ScenarioName", "").strip()
                    year_str = row.get("Year", "").strip()
                    age_str = row.get("Age", "").strip()
                    balance_str = row.get("ProjectedBalance", "0").replace("$", "").replace(",", "").strip()
                    income_str = row.get("ProjectedIncome", "0").replace("$", "").replace(",", "").strip()
                    withdrawal_str = row.get("WithdrawalAmount", "0").replace("$", "").replace(",", "").strip()

                    if not scenario_name:
                        continue

                    try:
                        year = int(year_str) if year_str else None
                        age = int(age_str) if age_str else None
                        balance = float(balance_str) if balance_str else 0.0
                        income = float(income_str) if income_str else 0.0
                        withdrawal = float(withdrawal_str) if withdrawal_str else 0.0
                    except ValueError:
                        continue

                    projection = {
                        "scenario": scenario_name,
                        "year": year,
                        "age": age,
                        "projected_balance": balance,
                        "projected_income": income,
                        "withdrawal_amount": withdrawal,
                        "notes": row.get("Notes", "").strip(),
                    }
                    projections.append(projection)

                except Exception as e:
                    print(f"Warning: Skipping projection row: {e}")
                    continue

        return projections

    def get_goals(self) -> List[FinancialGoal]:
        """Return all imported goals."""
        return self._goals

    def get_plan_documents(self) -> List[ComplianceDocument]:
        """Return all imported plan metadata as documents."""
        return self._plan_documents
