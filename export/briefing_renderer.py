"""
Briefing Renderer — Export ReviewBriefing to multiple formats.

Formats:
- Markdown: Clean, readable for email/documentation
- Text: Professional 2-page layout for printing
"""

from datetime import datetime
from src.review_assembler import ReviewBriefing, FlagSeverity


class BriefingRenderer:
    """Renders briefings in different output formats."""

    def __init__(self, firm_name: str = "Your Firm", advisor_name: str = ""):
        self.firm_name = firm_name
        self.advisor_name = advisor_name

    def render_markdown(self, briefing: ReviewBriefing) -> str:
        """Render briefing as clean Markdown."""
        lines = []

        # Header
        lines.append(f"# Client Review Briefing")
        lines.append(f"## {briefing.household_name}")
        lines.append("")
        lines.append(f"**Primary Contact:** {briefing.primary_contact}")
        lines.append(f"**Service Tier:** {briefing.service_tier.upper()}")
        lines.append(f"**Advisor:** {briefing.advisor}")
        lines.append(f"**Meeting Date:** {briefing.meeting_date or 'TBD'}")
        lines.append(f"**Client Since:** {briefing.client_since or 'N/A'} ({briefing.relationship_years or '?'} years)")
        lines.append(f"**Last Review:** {briefing.last_review_date or 'N/A'}")
        lines.append("")

        # Flags
        if briefing.flags:
            lines.append("## Attention Flags")
            lines.append("")
            for flag in briefing.flags:
                severity_mark = "🔴" if flag.severity == FlagSeverity.HIGH else "🟡" if flag.severity == FlagSeverity.MEDIUM else "🟢"
                lines.append(f"### {severity_mark} {flag.title}")
                lines.append(f"__{flag.detail}__")
                if flag.recommended_action:
                    lines.append(f"**Action:** {flag.recommended_action}")
                lines.append("")

        # Household
        lines.append("## Household Context")
        lines.append("")
        if briefing.household_context.get("members"):
            for member in briefing.household_context["members"]:
                retired_note = " (Retired)" if member.get("retired") else ""
                lines.append(f"- **{member['name']}** — {member['relationship'].title()}, Age {member.get('age', 'N/A')}{retired_note}")
                if member.get("occupation"):
                    lines.append(f"  - Occupation: {member['occupation']}")
        lines.append("")
        lines.append(f"**Risk Tolerance:** {briefing.household_context.get('risk_tolerance', 'N/A')}")
        lines.append(f"**Investment Objective:** {briefing.household_context.get('investment_objective', 'N/A')}")
        lines.append(f"**Time Horizon:** {briefing.household_context.get('time_horizon', 'N/A')}")
        lines.append("")

        # Life Events
        if briefing.life_events:
            lines.append("## Life Events Since Last Review")
            lines.append("")
            for event in briefing.life_events:
                lines.append(f"### {event['category'].replace('_', ' ').title()}")
                lines.append(f"**Date:** {event['date']}")
                if event.get('member'):
                    lines.append(f"**Member:** {event['member']}")
                lines.append(f"\n{event['description']}")
                if event.get('planning_impact'):
                    lines.append(f"\n💡 **Planning Impact:** {event['planning_impact']}")
                lines.append("")

        # Portfolio
        if briefing.portfolio_summary:
            p = briefing.portfolio_summary
            lines.append("## Portfolio Summary")
            lines.append("")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Current AUM | ${p['total_aum']:,.0f} |")
            lines.append(f"| Previous AUM | ${p['aum_change'] + p['total_aum']:,.0f} |")
            lines.append(f"| Change | ${p['aum_change']:+,.0f} ({p['aum_change_pct']:+.1f}%) |")
            lines.append(f"| Period Return | {p['period_return_pct']:+.1f}% |")
            lines.append(f"| Benchmark | {p['benchmark_return_pct']:+.1f}% ({p['benchmark_name']}) |")
            lines.append(f"| Excess Return | {p['excess_return_pct']:+.1f}% |")
            lines.append("")

            if p.get('allocation'):
                lines.append("### Asset Allocation")
                lines.append("")
                lines.append(f"| Asset Class | Target | Actual | Drift |")
                lines.append(f"|-------------|--------|--------|-------|")
                for a in p['allocation']:
                    drift_mark = " ⚠️" if a['needs_rebalance'] else ""
                    lines.append(
                        f"| {a['asset_class']} | {a['target_pct']:.1f}% | "
                        f"{a['actual_pct']:.1f}% | {a['drift_pct']:+.1f}%{drift_mark} |"
                    )
                lines.append("")

                if p.get('rebalance_needed'):
                    lines.append("**Rebalance Recommended:**")
                    for item in p.get('rebalance_items', []):
                        lines.append(f"- {item}")
                    lines.append("")

        # Goals
        if briefing.goals:
            lines.append("## Financial Goals")
            lines.append("")
            for goal in briefing.goals:
                status_icon = "✅" if goal['status'] == 'on_track' else "⚠️" if goal['status'] == 'at_risk' else "❌"
                lines.append(f"### {status_icon} {goal['name']}")
                if goal.get('target_amount'):
                    lines.append(f"- **Target:** ${goal['target_amount']:,.0f} by {goal.get('target_date', 'TBD')}")
                lines.append(f"- **Status:** {goal['status'].replace('_', ' ').title()}")
                lines.append(f"- **Funded:** {goal['funded_pct']}%")
                if goal.get('notes'):
                    lines.append(f"- **Notes:** {goal['notes']}")
                lines.append("")

        # Compliance
        if briefing.compliance_items:
            action_required = [item for item in briefing.compliance_items if item['status'] in ('expired', 'expiring', 'missing')]
            if action_required:
                lines.append("## Compliance — Action Required")
                lines.append("")
                for item in action_required:
                    lines.append(f"### {item['document_type'].upper()}")
                    lines.append(f"**Status:** {item['status'].replace('_', ' ').title()}")
                    if item.get('days_until_expiry'):
                        days = item['days_until_expiry']
                        if days > 0:
                            lines.append(f"**Expires in:** {days} days ({item['expiration']})")
                        else:
                            lines.append(f"**EXPIRED:** {item['expiration']}")
                    if item.get('notes'):
                        lines.append(f"**Note:** {item['notes']}")
                    lines.append("")

        # Action Items
        if briefing.action_items:
            lines.append("## Open Action Items")
            lines.append("")
            for item in briefing.action_items:
                overdue_tag = " 🔴 **OVERDUE**" if item['is_overdue'] else ""
                lines.append(f"### {item['priority'].upper()}: {item['description']}{overdue_tag}")
                lines.append(f"- **Assigned to:** {item['assigned_to']}")
                lines.append(f"- **Status:** {item['status'].replace('_', ' ').title()}")
                lines.append(f"- **Due:** {item.get('due_date', 'N/A')}")
                if item['is_overdue']:
                    lines.append(f"- **OVERDUE:** {item['days_overdue']} days")
                if item.get('notes'):
                    lines.append(f"- **Note:** {item['notes']}")
                lines.append("")

        # Conversation Starters
        if briefing.conversation_starters:
            lines.append("## Conversation Starters")
            lines.append("")
            for i, starter in enumerate(briefing.conversation_starters, 1):
                lines.append(f"{i}. {starter}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append(f"*Briefing ID: {briefing.household_id} | Status: {briefing.status.value}*")

        return "\n".join(lines)

    def render_text(self, briefing: ReviewBriefing, page_width: int = 80) -> str:
        """Render briefing as professional 2-page text format."""
        lines = []

        # PAGE 1: Header, Flags, Portfolio
        lines.append("=" * page_width)
        lines.append(f"CLIENT REVIEW BRIEFING".center(page_width))
        lines.append(f"{self.firm_name}".center(page_width))
        lines.append("=" * page_width)
        lines.append("")

        # Header info
        lines.append(f"Client:        {briefing.household_name}")
        lines.append(f"Primary:       {briefing.primary_contact}")
        lines.append(f"Tier:          {briefing.service_tier.upper()}")
        lines.append(f"Advisor:       {briefing.advisor}")
        lines.append(f"Meeting Date:  {briefing.meeting_date or 'TBD'}")
        lines.append(f"Since:         {briefing.client_since or 'N/A'} ({briefing.relationship_years or '?'} years)")
        lines.append("")

        # High-priority flags
        high_flags = [f for f in briefing.flags if f.severity == FlagSeverity.HIGH]
        if high_flags:
            lines.append("-" * page_width)
            lines.append(f"⚠️  ATTENTION REQUIRED ({len(high_flags)} items)")
            lines.append("-" * page_width)
            for flag in high_flags:
                lines.append(f"  • {flag.title}")
                # Wrap detail text
                detail_lines = self._wrap_text(flag.detail, page_width - 6)
                for detail_line in detail_lines:
                    lines.append(f"    {detail_line}")
                if flag.recommended_action:
                    action_lines = self._wrap_text(flag.recommended_action, page_width - 6)
                    lines.append(f"    → Action: {action_lines[0]}")
                    for action_line in action_lines[1:]:
                        lines.append(f"      {action_line}")
                lines.append("")

        # Portfolio snapshot
        if briefing.portfolio_summary:
            p = briefing.portfolio_summary
            lines.append("-" * page_width)
            lines.append("PORTFOLIO SUMMARY")
            lines.append("-" * page_width)
            lines.append(f"  AUM:                 ${p['total_aum']:>15,.0f}")
            lines.append(f"  Change:              ${p['aum_change']:>15,.0f} ({p['aum_change_pct']:>+5.1f}%)")
            lines.append(f"  Period Return:       {p['period_return_pct']:>15+.1f}%")
            lines.append(f"  Benchmark:           {p['benchmark_return_pct']:>15+.1f}% ({p['benchmark_name']})")
            lines.append(f"  Excess Return:       {p['excess_return_pct']:>15+.1f}%")
            lines.append("")

            if p.get('allocation'):
                lines.append("  Asset Allocation:")
                lines.append(f"  {'Class':<20} {'Target':>8} {'Actual':>8} {'Drift':>8}")
                lines.append(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")
                for a in p['allocation']:
                    flag_mark = " ⚠️" if a['needs_rebalance'] else ""
                    lines.append(
                        f"  {a['asset_class']:<20} {a['target_pct']:>7.1f}% {a['actual_pct']:>7.1f}% {a['drift_pct']:>+7.1f}%{flag_mark}"
                    )
                lines.append("")

        # Life events summary
        if briefing.life_events:
            lines.append("-" * page_width)
            lines.append(f"LIFE EVENTS ({len(briefing.life_events)})")
            lines.append("-" * page_width)
            for event in briefing.life_events:
                lines.append(f"  • {event['category'].replace('_', ' ').upper()} ({event['date']})")
                desc_lines = self._wrap_text(event['description'], page_width - 6)
                for desc_line in desc_lines:
                    lines.append(f"    {desc_line}")
                lines.append("")

        # PAGE 2: Compliance, Action Items, Conversation Starters
        lines.append("\f")  # Form feed (page break)
        lines.append("")
        lines.append("=" * page_width)
        lines.append(f"CLIENT REVIEW BRIEFING (continued)".center(page_width))
        lines.append("=" * page_width)
        lines.append(f"{briefing.household_name}  |  {briefing.advisor}  |  {briefing.meeting_date or 'TBD'}")
        lines.append("")

        # Compliance
        if briefing.compliance_items:
            action_required = [item for item in briefing.compliance_items if item['status'] in ('expired', 'expiring', 'missing')]
            if action_required:
                lines.append("-" * page_width)
                lines.append(f"COMPLIANCE — ACTION REQUIRED ({len(action_required)} items)")
                lines.append("-" * page_width)
                for item in action_required:
                    status = item['status'].upper()
                    if item.get('days_until_expiry'):
                        if item['days_until_expiry'] <= 0:
                            status = "EXPIRED"
                        else:
                            status = f"EXPIRES IN {item['days_until_expiry']} DAYS"
                    lines.append(f"  • {item['document_type'].upper()}: {status}")
                    if item.get('notes'):
                        note_lines = self._wrap_text(item['notes'], page_width - 6)
                        for note_line in note_lines:
                            lines.append(f"    {note_line}")
                lines.append("")

        # Action Items
        if briefing.action_items:
            lines.append("-" * page_width)
            lines.append(f"OPEN ACTION ITEMS ({len(briefing.action_items)})")
            lines.append("-" * page_width)
            for item in briefing.action_items:
                overdue_tag = " [OVERDUE]" if item['is_overdue'] else ""
                lines.append(f"  • [{item['priority'].upper()}] {item['description']}{overdue_tag}")
                lines.append(f"    Assigned: {item['assigned_to']} | Due: {item.get('due_date', 'N/A')}")
                if item.get('notes'):
                    lines.append(f"    Note: {item['notes']}")
                lines.append("")

        # Goals Summary
        if briefing.goals:
            at_risk = [g for g in briefing.goals if g['status'] == 'at_risk']
            if at_risk:
                lines.append("-" * page_width)
                lines.append("GOALS AT RISK")
                lines.append("-" * page_width)
                for goal in at_risk:
                    lines.append(f"  • {goal['name']}")
                    if goal.get('target_amount'):
                        lines.append(f"    Target: ${goal['target_amount']:,.0f} by {goal.get('target_date', 'TBD')}")
                    lines.append(f"    Funded: {goal['funded_pct']}%")
                    if goal.get('notes'):
                        lines.append(f"    Note: {goal['notes']}")
                    lines.append("")

        # Conversation Starters
        if briefing.conversation_starters:
            lines.append("-" * page_width)
            lines.append("CONVERSATION STARTERS")
            lines.append("-" * page_width)
            for i, starter in enumerate(briefing.conversation_starters, 1):
                starter_lines = self._wrap_text(starter, page_width - 6)
                lines.append(f"  {i}. {starter_lines[0]}")
                for starter_line in starter_lines[1:]:
                    lines.append(f"     {starter_line}")
            lines.append("")

        # Footer
        lines.append("=" * page_width)
        lines.append(f"CONFIDENTIAL - FOR ADVISOR USE ONLY".center(page_width))
        lines.append(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | ID: {briefing.household_id}".center(page_width))
        lines.append("=" * page_width)

        return "\n".join(lines)

    @staticmethod
    def _wrap_text(text: str, width: int) -> list:
        """Wrap text to specified width."""
        if not text:
            return []

        lines = []
        current_line = ""

        for word in text.split():
            if len(current_line) + len(word) + 1 <= width:
                current_line += (word + " ") if current_line else word
            else:
                if current_line:
                    lines.append(current_line.rstrip())
                current_line = word

        if current_line:
            lines.append(current_line.rstrip())

        return lines

    def export_markdown(self, briefing: ReviewBriefing, output_path: str) -> str:
        """Export briefing to Markdown file."""
        content = self.render_markdown(briefing)
        with open(output_path, 'w') as f:
            f.write(content)
        return output_path

    def export_text(self, briefing: ReviewBriefing, output_path: str) -> str:
        """Export briefing to text file."""
        content = self.render_text(briefing)
        with open(output_path, 'w') as f:
            f.write(content)
        return output_path
