"""
CRM Importer — Reads Salesforce/Redtail contact export CSV files.

Maps contact demographics, meeting history, and notes into HouseholdMember
and Interaction objects.
"""

import csv
from datetime import date, datetime
from typing import Optional, List, Dict, Tuple

from src.client_profiler import (
    HouseholdMember,
    Interaction,
)


class CRMImporter:
    """Imports contact and interaction data from CRM CSV exports."""

    def __init__(self):
        self._contacts: List[HouseholdMember] = []
        self._interactions: List[Interaction] = []

    def import_contacts(
        self,
        csv_file: str,
        custodian: str = "Schwab",
    ) -> List[HouseholdMember]:
        """Import household members from CRM contact CSV.

        Expected columns:
        - FirstName, LastName
        - DateOfBirth (optional)
        - Email, PhoneNumber
        - Employer, Occupation
        - IsRetired (Y/N), RetirementDate (optional)
        - Relationship (primary, spouse, child, etc.)
        - Notes
        """
        contacts = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    first_name = row.get("FirstName", "").strip()
                    last_name = row.get("LastName", "").strip()
                    full_name = f"{first_name} {last_name}".strip()

                    if not full_name:
                        continue

                    # Parse dates
                    dob_str = row.get("DateOfBirth", "").strip()
                    try:
                        dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None
                    except (ValueError, TypeError):
                        dob = None

                    retirement_date_str = row.get("RetirementDate", "").strip()
                    try:
                        retirement_date = (
                            datetime.strptime(retirement_date_str, "%Y-%m-%d").date()
                            if retirement_date_str else None
                        )
                    except (ValueError, TypeError):
                        retirement_date = None

                    # Parse boolean
                    is_retired_str = row.get("IsRetired", "N").strip().upper()
                    is_retired = is_retired_str in ("Y", "YES", "TRUE", "1")

                    member = HouseholdMember(
                        name=full_name,
                        relationship=row.get("Relationship", "primary").strip().lower(),
                        date_of_birth=dob,
                        email=row.get("Email", "").strip() or None,
                        phone=row.get("PhoneNumber", "").strip() or None,
                        employer=row.get("Employer", "").strip() or None,
                        occupation=row.get("Occupation", "").strip() or None,
                        is_retired=is_retired,
                        retirement_date=retirement_date,
                        health_notes=row.get("HealthNotes", "").strip() or None,
                        notes=row.get("Notes", "").strip(),
                    )
                    contacts.append(member)

                except Exception as e:
                    print(f"Warning: Skipping contact row: {e}")
                    continue

        self._contacts.extend(contacts)
        return contacts

    def import_interactions(
        self,
        csv_file: str,
    ) -> List[Interaction]:
        """Import meeting/interaction history from CRM.

        Expected columns:
        - ContactName (or FirstName/LastName)
        - InteractionType (email, phone, meeting, document_signed, portal_login)
        - InteractionDate
        - Direction (outbound, inbound)
        - InitiatedBy (staff name or 'client')
        - Summary (optional)
        - ResponseTimeHours (optional)
        """
        interactions = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    date_str = row.get("InteractionDate", "").strip()
                    try:
                        interaction_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        continue

                    interaction_type = row.get("InteractionType", "email").strip().lower()
                    direction = row.get("Direction", "outbound").strip().lower()
                    initiated_by = row.get("InitiatedBy", "").strip()
                    summary = row.get("Summary", "").strip() or None
                    response_time_str = row.get("ResponseTimeHours", "").strip()

                    try:
                        response_time = float(response_time_str) if response_time_str else None
                    except ValueError:
                        response_time = None

                    # Normalize direction
                    if direction not in ("inbound", "outbound"):
                        direction = "outbound" if initiated_by != "client" else "inbound"

                    interaction = Interaction(
                        date=interaction_date,
                        interaction_type=interaction_type,
                        direction=direction,
                        initiated_by=initiated_by or "staff",
                        summary=summary,
                        response_time_hours=response_time,
                    )
                    interactions.append(interaction)

                except Exception as e:
                    print(f"Warning: Skipping interaction row: {e}")
                    continue

        self._interactions.extend(interactions)
        return interactions

    def import_notes(
        self,
        csv_file: str,
    ) -> List[Dict]:
        """Import CRM notes for enrichment.

        Expected columns:
        - ContactName
        - NoteDate
        - Note
        - Category (optional: life_event, compliance, action_item, etc.)
        """
        notes = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    contact_name = row.get("ContactName", "").strip()
                    note_date_str = row.get("NoteDate", "").strip()
                    note_text = row.get("Note", "").strip()
                    category = row.get("Category", "general").strip()

                    if not contact_name or not note_text:
                        continue

                    try:
                        note_date = datetime.strptime(note_date_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        note_date = date.today()

                    notes.append({
                        "contact_name": contact_name,
                        "date": note_date,
                        "text": note_text,
                        "category": category,
                    })

                except Exception as e:
                    print(f"Warning: Skipping note row: {e}")
                    continue

        return notes

    def get_contacts(self) -> List[HouseholdMember]:
        """Return all imported contacts."""
        return self._contacts

    def get_interactions(self) -> List[Interaction]:
        """Return all imported interactions."""
        return self._interactions
