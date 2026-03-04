"""
Custodial Portfolio Importer — Reads Schwab/Fidelity portfolio export CSV files.

Supports multiple custodian formats for positions, transactions, and performance data.
Maps CSV columns to the Account, PerformanceSnapshot, and AssetAllocation models.
"""

import csv
from datetime import date, datetime
from typing import Optional, List, Dict
from dataclasses import dataclass

from src.client_profiler import (
    Account,
    AccountType,
    PerformanceSnapshot,
    AssetAllocation,
)


@dataclass
class PositionImportConfig:
    """Column mapping for positions CSV."""
    account_number_col: str
    account_type_col: str
    custodian_col: str
    owner_col: str
    balance_col: str
    date_col: str
    symbol_col: Optional[str] = None
    quantity_col: Optional[str] = None
    model_portfolio_col: Optional[str] = None


@dataclass
class TransactionImportConfig:
    """Column mapping for transactions CSV."""
    account_number_col: str
    transaction_type_col: str
    date_col: str
    amount_col: str
    description_col: str
    symbol_col: Optional[str] = None


class SchwabPositionConfig(PositionImportConfig):
    """Schwab CSV export column mapping."""
    def __init__(self):
        super().__init__(
            account_number_col="AccountNumber",
            account_type_col="AccountType",
            custodian_col="Custodian",
            owner_col="Owner",
            balance_col="MarketValue",
            date_col="AsOfDate",
            symbol_col="Symbol",
            quantity_col="Quantity",
            model_portfolio_col="ModelPortfolio",
        )


class FidelityPositionConfig(PositionImportConfig):
    """Fidelity CSV export column mapping."""
    def __init__(self):
        super().__init__(
            account_number_col="Account Number",
            account_type_col="Account Type",
            custodian_col="Custodian",
            owner_col="Account Owner",
            balance_col="Market Value",
            date_col="As of Date",
        )


class CustodialImporter:
    """Imports portfolio data from custodian CSV exports."""

    ACCOUNT_TYPE_MAP = {
        "Joint": AccountType.JOINT,
        "Individual": AccountType.INDIVIDUAL,
        "Traditional IRA": AccountType.TRADITIONAL_IRA,
        "Roth IRA": AccountType.ROTH_IRA,
        "SEP IRA": AccountType.SEP_IRA,
        "Rollover IRA": AccountType.ROLLOVER_IRA,
        "Trust": AccountType.TRUST,
        "UTMA/UGMA": AccountType.CUSTODIAL,
        "529": AccountType.EDUCATION_529,
        "Brokerage": AccountType.INDIVIDUAL,
        "Retirement": AccountType.TRADITIONAL_IRA,
    }

    def __init__(self):
        self._accounts: List[Account] = []
        self._performance_snapshots: List[PerformanceSnapshot] = []
        self._allocations: List[AssetAllocation] = []

    def import_positions(
        self,
        csv_file: str,
        config: Optional[PositionImportConfig] = None,
    ) -> List[Account]:
        """Import portfolio positions from CSV file."""
        if config is None:
            config = SchwabPositionConfig()

        accounts = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            account_map = {}  # Consolidate positions to account level

            for row in reader:
                try:
                    acct_num = row.get(config.account_number_col, "").strip()
                    acct_type_str = row.get(config.account_type_col, "Individual").strip()
                    owner = row.get(config.owner_col, "Unknown").strip()
                    balance_str = row.get(config.balance_col, "0").replace("$", "").replace(",", "")
                    date_str = row.get(config.date_col, date.today().isoformat()).strip()

                    # Parse balance
                    try:
                        balance = float(balance_str)
                    except ValueError:
                        balance = 0.0

                    # Parse date
                    try:
                        if isinstance(date_str, str):
                            balance_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        else:
                            balance_date = date_str
                    except (ValueError, TypeError):
                        balance_date = date.today()

                    # Map account type
                    account_type = self.ACCOUNT_TYPE_MAP.get(
                        acct_type_str, AccountType.INDIVIDUAL
                    )

                    # Consolidate by account number
                    if acct_num not in account_map:
                        account_map[acct_num] = {
                            "id": acct_num,
                            "account_type": account_type,
                            "owner": owner,
                            "custodian": row.get(config.custodian_col, "Schwab").strip(),
                            "balance": balance,
                            "date": balance_date,
                            "model_portfolio": row.get(config.model_portfolio_col),
                        }
                    else:
                        # Accumulate balances if multiple rows per account
                        account_map[acct_num]["balance"] += balance

                except (KeyError, ValueError) as e:
                    print(f"Warning: Skipping row due to parsing error: {e}")
                    continue

            # Create Account objects
            for acct_data in account_map.values():
                account = Account(
                    id=acct_data["id"],
                    account_type=acct_data["account_type"],
                    owner=acct_data["owner"],
                    custodian=acct_data["custodian"],
                    current_balance=acct_data["balance"],
                    balance_as_of=acct_data["date"],
                    is_managed=True,
                    model_portfolio=acct_data.get("model_portfolio"),
                )
                accounts.append(account)

        self._accounts.extend(accounts)
        return accounts

    def import_transactions(
        self,
        csv_file: str,
        config: Optional[TransactionImportConfig] = None,
    ) -> List[Dict]:
        """Import transactions from CSV for flow analysis.

        Returns list of transaction dicts with standardized fields.
        """
        if config is None:
            config = TransactionImportConfig(
                account_number_col="AccountNumber",
                account_type_col="TransactionType",
                date_col="TransactionDate",
                amount_col="Amount",
                description_col="Description",
            )

        transactions = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    acct_num = row.get(config.account_number_col, "").strip()
                    tx_type = row.get(config.transaction_type_col, "Other").strip()
                    date_str = row.get(config.date_col, "").strip()
                    amount_str = row.get(config.amount_col, "0").replace("$", "").replace(",", "")
                    description = row.get(config.description_col, "").strip()

                    # Parse amount (negative for withdrawals)
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        amount = 0.0

                    # Parse date
                    try:
                        tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        tx_date = date.today()

                    transaction = {
                        "account_number": acct_num,
                        "type": tx_type,
                        "date": tx_date,
                        "amount": amount,
                        "description": description,
                    }
                    transactions.append(transaction)

                except Exception as e:
                    print(f"Warning: Skipping transaction row: {e}")
                    continue

        return transactions

    def import_performance(
        self,
        csv_file: str,
        period_label: str = "Period",
    ) -> List[PerformanceSnapshot]:
        """Import performance data from CSV."""
        snapshots = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    period_start_str = row.get("PeriodStart", "").strip()
                    period_end_str = row.get("PeriodEnd", "").strip()
                    portfolio_return_str = row.get("PortfolioReturn", "0").strip("%")
                    benchmark_return_str = row.get("BenchmarkReturn", "0").strip("%")
                    benchmark_name = row.get("Benchmark", "60/40 Blend").strip()
                    net_flows_str = row.get("NetFlows", "0").replace("$", "").replace(",", "")
                    beginning_value_str = row.get("BeginningValue", "0").replace("$", "").replace(",", "")
                    ending_value_str = row.get("EndingValue", "0").replace("$", "").replace(",", "")

                    # Parse dates
                    try:
                        period_start = datetime.strptime(period_start_str, "%Y-%m-%d").date()
                        period_end = datetime.strptime(period_end_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        continue

                    # Parse floats
                    try:
                        portfolio_return = float(portfolio_return_str)
                        benchmark_return = float(benchmark_return_str)
                        net_flows = float(net_flows_str)
                        beginning_value = float(beginning_value_str)
                        ending_value = float(ending_value_str)
                    except ValueError:
                        continue

                    snapshot = PerformanceSnapshot(
                        period_label=period_label,
                        period_start=period_start,
                        period_end=period_end,
                        portfolio_return_pct=portfolio_return,
                        benchmark_return_pct=benchmark_return,
                        benchmark_name=benchmark_name,
                        net_flows=net_flows,
                        beginning_value=beginning_value,
                        ending_value=ending_value,
                    )
                    snapshots.append(snapshot)

                except Exception as e:
                    print(f"Warning: Skipping performance row: {e}")
                    continue

        self._performance_snapshots.extend(snapshots)
        return snapshots

    def import_allocations(
        self,
        csv_file: str,
    ) -> List[AssetAllocation]:
        """Import asset allocation target vs. actual from CSV."""
        allocations = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    asset_class = row.get("AssetClass", "").strip()
                    target_str = row.get("TargetPercent", "0").strip("%")
                    actual_str = row.get("ActualPercent", "0").strip("%")
                    market_value_str = row.get("MarketValue", "0").replace("$", "").replace(",", "")

                    # Parse floats
                    try:
                        target_pct = float(target_str)
                        actual_pct = float(actual_str)
                        market_value = float(market_value_str)
                    except ValueError:
                        continue

                    allocation = AssetAllocation(
                        asset_class=asset_class,
                        target_pct=target_pct,
                        actual_pct=actual_pct,
                        market_value=market_value,
                    )
                    allocations.append(allocation)

                except Exception as e:
                    print(f"Warning: Skipping allocation row: {e}")
                    continue

        self._allocations.extend(allocations)
        return allocations

    def get_accounts(self) -> List[Account]:
        """Return all imported accounts."""
        return self._accounts

    def get_performance(self) -> List[PerformanceSnapshot]:
        """Return all imported performance snapshots."""
        return self._performance_snapshots

    def get_allocations(self) -> List[AssetAllocation]:
        """Return all imported allocations."""
        return self._allocations
