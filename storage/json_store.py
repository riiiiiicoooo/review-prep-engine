"""
JSON Persistence Layer — Serializes/deserializes client data to JSON.

Provides a lightweight persistence mechanism without external dependencies.
Organizes data hierarchically: data/households/{household_id}/briefings/{date}.json
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
import zipfile
import shutil

from src.client_profiler import (
    ClientHousehold,
    HouseholdMember,
    Account,
    PerformanceSnapshot,
    AssetAllocation,
    LifeEvent,
    FinancialGoal,
    ComplianceDocument,
    ActionItem,
    ReviewRecord,
    Interaction,
    ServiceTier,
    AccountType,
    LifeEventCategory,
    GoalStatus,
    DocumentType,
    ActionItemStatus,
    ActionItemPriority,
)
from src.review_assembler import ReviewBriefing, BriefingStatus


class EnumEncoder(json.JSONEncoder):
    """JSON encoder that handles Enum values."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)


def dataclass_to_dict(obj: Any) -> Dict:
    """Convert a dataclass to a dictionary, handling nested enums and dates."""
    if is_dataclass(obj):
        result = {}
        for field in fields(obj):
            value = getattr(obj, field.name)
            if isinstance(value, Enum):
                result[field.name] = value.value
            elif isinstance(value, (date, datetime)):
                result[field.name] = value.isoformat()
            elif is_dataclass(value):
                result[field.name] = dataclass_to_dict(value)
            elif isinstance(value, list):
                result[field.name] = [dataclass_to_dict(v) if is_dataclass(v) else v for v in value]
            else:
                result[field.name] = value
        return result
    return obj


def dict_to_dataclass(data: Dict, dataclass_type: type) -> Any:
    """Convert a dictionary back to a dataclass, handling enums and dates."""
    if not isinstance(data, dict):
        return data

    kwargs = {}
    for field in fields(dataclass_type):
        field_name = field.name
        field_type = field.type

        if field_name not in data:
            continue

        value = data[field_name]

        # Handle Optional types
        if hasattr(field_type, '__origin__') and field_type.__origin__ is type(None).__class__.__bases__[0]:
            inner_type = field_type.__args__[0]
            if value is None:
                kwargs[field_name] = None
                continue
            field_type = inner_type
        elif hasattr(field_type, '__args__') and type(None) in field_type.__args__:
            inner_type = [t for t in field_type.__args__ if t is not type(None)][0]
            if value is None:
                kwargs[field_name] = None
                continue
            field_type = inner_type

        # Convert strings to enums
        if isinstance(field_type, type) and issubclass(field_type, Enum):
            kwargs[field_name] = field_type(value)
        # Convert strings to dates
        elif field_type in (date, datetime):
            if isinstance(value, str):
                if field_type == date:
                    kwargs[field_name] = datetime.fromisoformat(value).date()
                else:
                    kwargs[field_name] = datetime.fromisoformat(value)
            else:
                kwargs[field_name] = value
        # Handle lists of dataclasses
        elif hasattr(field_type, '__origin__') and field_type.__origin__ is list:
            if field_type.__args__ and is_dataclass(field_type.__args__[0]):
                kwargs[field_name] = [dict_to_dataclass(v, field_type.__args__[0]) for v in value]
            else:
                kwargs[field_name] = value
        # Handle nested dataclasses
        elif is_dataclass(field_type):
            kwargs[field_name] = dict_to_dataclass(value, field_type)
        else:
            kwargs[field_name] = value

    return dataclass_type(**kwargs)


class ActionItemTracker:
    """Tracks action item status changes over time."""

    def __init__(self, action_item: ActionItem):
        self.action_item_id = action_item.id
        self.description = action_item.description
        self.initial_status = action_item.status.value
        self.current_status = action_item.status.value
        self.created_date = action_item.created_date.isoformat()
        self.status_history: List[Dict] = [
            {
                "status": action_item.status.value,
                "changed_at": datetime.now().isoformat(),
                "notes": "",
            }
        ]

    def update_status(self, new_status: ActionItemStatus, notes: str = "") -> None:
        """Record a status change."""
        self.current_status = new_status.value
        self.status_history.append({
            "status": new_status.value,
            "changed_at": datetime.now().isoformat(),
            "notes": notes,
        })

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_item_id": self.action_item_id,
            "description": self.description,
            "initial_status": self.initial_status,
            "current_status": self.current_status,
            "created_date": self.created_date,
            "status_history": self.status_history,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ActionItemTracker":
        """Reconstruct from dictionary."""
        tracker = cls.__new__(cls)
        tracker.action_item_id = data["action_item_id"]
        tracker.description = data["description"]
        tracker.initial_status = data["initial_status"]
        tracker.current_status = data["current_status"]
        tracker.created_date = data["created_date"]
        tracker.status_history = data["status_history"]
        return tracker


class BriefingHistory:
    """Loads and manages historical briefings for delta calculations."""

    def __init__(self, store_dir: str):
        self.store_dir = Path(store_dir)
        self._cache: Dict[str, ReviewBriefing] = {}

    def load_briefing(self, household_id: str, briefing_date: date) -> Optional[ReviewBriefing]:
        """Load a specific briefing from disk."""
        briefing_path = (
            self.store_dir / "households" / household_id / "briefings"
            / f"{briefing_date.isoformat()}.json"
        )

        if not briefing_path.exists():
            return None

        try:
            with open(briefing_path, 'r') as f:
                data = json.load(f)
            return dict_to_dataclass(data, ReviewBriefing)
        except Exception as e:
            print(f"Error loading briefing {briefing_path}: {e}")
            return None

    def load_latest_briefing(self, household_id: str) -> Optional[ReviewBriefing]:
        """Load the most recent briefing for a household."""
        briefings_dir = self.store_dir / "households" / household_id / "briefings"

        if not briefings_dir.exists():
            return None

        # Find all briefing files and sort by date
        briefing_files = sorted(briefings_dir.glob("*.json"), reverse=True)

        if not briefing_files:
            return None

        try:
            with open(briefing_files[0], 'r') as f:
                data = json.load(f)
            return dict_to_dataclass(data, ReviewBriefing)
        except Exception as e:
            print(f"Error loading latest briefing: {e}")
            return None

    def list_briefings(self, household_id: str) -> List[Dict]:
        """List all briefings for a household with metadata."""
        briefings_dir = self.store_dir / "households" / household_id / "briefings"

        if not briefings_dir.exists():
            return []

        briefings = []
        for briefing_file in sorted(briefings_dir.glob("*.json"), reverse=True):
            try:
                with open(briefing_file, 'r') as f:
                    data = json.load(f)
                briefings.append({
                    "date": briefing_file.stem,
                    "status": data.get("status", "unknown"),
                    "high_flags": data.get("high_priority_count", 0),
                    "medium_flags": data.get("medium_priority_count", 0),
                })
            except Exception as e:
                print(f"Error reading briefing {briefing_file}: {e}")
                continue

        return briefings


class JSONStore:
    """JSON-based persistence for client data."""

    def __init__(self, store_dir: str = "data"):
        """Initialize store with base directory path."""
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.history = BriefingHistory(store_dir)
        self._action_item_trackers: Dict[str, ActionItemTracker] = {}

    def save_household(self, household: ClientHousehold) -> Path:
        """Save a household profile to JSON."""
        household_dir = self.store_dir / "households" / household.id
        household_dir.mkdir(parents=True, exist_ok=True)

        household_file = household_dir / "profile.json"
        data = dataclass_to_dict(household)

        with open(household_file, 'w') as f:
            json.dump(data, f, cls=EnumEncoder, indent=2)

        return household_file

    def load_household(self, household_id: str) -> Optional[ClientHousehold]:
        """Load a household profile from JSON."""
        household_file = self.store_dir / "households" / household_id / "profile.json"

        if not household_file.exists():
            return None

        try:
            with open(household_file, 'r') as f:
                data = json.load(f)
            return dict_to_dataclass(data, ClientHousehold)
        except Exception as e:
            print(f"Error loading household {household_id}: {e}")
            return None

    def save_briefing(self, briefing: ReviewBriefing) -> Path:
        """Save a briefing to JSON."""
        briefing_dir = (
            self.store_dir / "households" / briefing.household_id / "briefings"
        )
        briefing_dir.mkdir(parents=True, exist_ok=True)

        briefing_file = briefing_dir / f"{briefing.meeting_date or date.today()}.json"
        data = dataclass_to_dict(briefing)

        with open(briefing_file, 'w') as f:
            json.dump(data, f, cls=EnumEncoder, indent=2)

        return briefing_file

    def load_briefing(
        self, household_id: str, briefing_date: Optional[date] = None
    ) -> Optional[ReviewBriefing]:
        """Load a briefing from JSON."""
        if briefing_date is None:
            return self.history.load_latest_briefing(household_id)
        return self.history.load_briefing(household_id, briefing_date)

    def save_engagement(self, engagement_data: Dict) -> Path:
        """Save engagement scoring results."""
        engagement_dir = self.store_dir / "engagement"
        engagement_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat()
        engagement_file = engagement_dir / f"{timestamp}.json"

        with open(engagement_file, 'w') as f:
            json.dump(engagement_data, f, indent=2)

        return engagement_file

    def load_engagement(self, household_id: str) -> Optional[Dict]:
        """Load the latest engagement score for a household."""
        engagement_dir = self.store_dir / "engagement"

        if not engagement_dir.exists():
            return None

        # Find files mentioning this household (simplified search)
        for engagement_file in sorted(engagement_dir.glob("*.json"), reverse=True):
            try:
                with open(engagement_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for entry in data:
                        if entry.get("household_id") == household_id:
                            return entry
                elif isinstance(data, dict) and data.get("household_id") == household_id:
                    return data
            except Exception as e:
                print(f"Error reading engagement file: {e}")
                continue

        return None

    def list_engagements(self) -> List[Dict]:
        """List all households with their engagement data."""
        engagement_dir = self.store_dir / "engagement"

        if not engagement_dir.exists():
            return []

        engagements = []
        for engagement_file in sorted(engagement_dir.glob("*.json"), reverse=True):
            try:
                with open(engagement_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    engagements.extend(data)
                elif isinstance(data, dict):
                    engagements.append(data)
            except Exception as e:
                print(f"Error reading engagement file: {e}")
                continue

        # Deduplicate by household (keep first/most recent)
        seen = set()
        unique = []
        for engagement in engagements:
            hh_id = engagement.get("household_id")
            if hh_id not in seen:
                unique.append(engagement)
                seen.add(hh_id)

        return unique

    def track_action_item(self, action_item: ActionItem) -> ActionItemTracker:
        """Start tracking an action item's status."""
        tracker = ActionItemTracker(action_item)
        self._action_item_trackers[action_item.id] = tracker
        return tracker

    def update_action_item_status(
        self, action_item_id: str, new_status: ActionItemStatus, notes: str = ""
    ) -> Optional[ActionItemTracker]:
        """Update an action item's status."""
        if action_item_id not in self._action_item_trackers:
            return None
        self._action_item_trackers[action_item_id].update_status(new_status, notes)
        return self._action_item_trackers[action_item_id]

    def get_action_item_history(self, action_item_id: str) -> Optional[Dict]:
        """Get the status history for an action item."""
        if action_item_id not in self._action_item_trackers:
            return None
        return self._action_item_trackers[action_item_id].to_dict()

    def backup_data(self, backup_path: Optional[str] = None) -> Path:
        """Create a ZIP backup of all stored data."""
        if backup_path is None:
            backup_path = self.store_dir.parent / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        else:
            backup_path = Path(backup_path)

        backup_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.store_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.store_dir.parent)
                    zipf.write(file_path, arcname)

        return backup_path

    def export_household_data(self, household_id: str, export_path: Optional[str] = None) -> Path:
        """Export all data for a household to a single JSON file."""
        export_data = {
            "household_id": household_id,
            "exported_at": datetime.now().isoformat(),
            "profile": None,
            "briefings": [],
            "engagement": None,
        }

        # Load profile
        household = self.load_household(household_id)
        if household:
            export_data["profile"] = dataclass_to_dict(household)

        # Load briefings
        briefings = self.history.list_briefings(household_id)
        for briefing_meta in briefings:
            briefing_date = datetime.fromisoformat(briefing_meta["date"]).date()
            briefing = self.load_briefing(household_id, briefing_date)
            if briefing:
                export_data["briefings"].append(dataclass_to_dict(briefing))

        # Load engagement
        engagement = self.load_engagement(household_id)
        if engagement:
            export_data["engagement"] = engagement

        # Write to file
        if export_path is None:
            export_path = (
                self.store_dir.parent
                / f"export_{household_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
        else:
            export_path = Path(export_path)

        export_path.parent.mkdir(parents=True, exist_ok=True)

        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        return export_path

    def list_households(self) -> List[str]:
        """List all household IDs in the store."""
        households_dir = self.store_dir / "households"

        if not households_dir.exists():
            return []

        return [d.name for d in households_dir.iterdir() if d.is_dir()]

    def delete_household(self, household_id: str) -> bool:
        """Delete all data for a household."""
        household_dir = self.store_dir / "households" / household_id

        if not household_dir.exists():
            return False

        try:
            shutil.rmtree(household_dir)
            return True
        except Exception as e:
            print(f"Error deleting household {household_id}: {e}")
            return False
