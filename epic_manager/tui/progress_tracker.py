"""
Progress Tracker Widget

Displays epic progress, statistics, and activity monitoring.
Provides visual indicators for completion status and real-time updates.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from textual.widget import Widget
from textual.widgets import ProgressBar, Static, DataTable, Log
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from rich.text import Text
from rich.console import Console

console = Console()


@dataclass
class EpicProgress:
    """Progress information for an epic."""
    epic_number: int
    title: str
    total_issues: int
    completed_issues: int
    in_progress_issues: int
    blocked_issues: int
    completion_percentage: float
    estimated_completion: Optional[str] = None
    last_activity: Optional[str] = None


@dataclass
class ActivityEvent:
    """Represents an activity event in the system."""
    timestamp: str
    epic_number: Optional[int]
    issue_number: Optional[int]
    event_type: str  # 'issue_started', 'pr_created', 'review_completed', etc.
    message: str
    level: str  # 'info', 'success', 'warning', 'error'
    instance: Optional[str] = None


class ProgressTracker(Widget):
    """Widget for tracking and displaying epic progress."""

    # Reactive attributes
    current_epic: reactive[Optional[int]] = reactive(None)
    show_all_epics: reactive[bool] = reactive(True)

    def __init__(self, *args, **kwargs) -> None:
        """Initialize progress tracker widget."""
        super().__init__(*args, **kwargs)

        # Progress data
        self.epic_progress: Dict[int, EpicProgress] = {}
        self.activity_history: List[ActivityEvent] = []
        self.max_activity_entries = 100

        # UI components
        self.progress_table: Optional[DataTable] = None
        self.activity_log: Optional[Log] = None
        self.summary_display: Optional[Static] = None

    def compose(self):
        """Compose the progress tracker widget."""
        # TODO: Implement widget composition
        # TODO: Create layout with progress bars and activity log
        # TODO: Set up data tables and summary displays

        with Vertical():
            # Summary section
            self.summary_display = Static("Epic Progress Summary", id="progress-summary")
            yield self.summary_display

            # Progress table
            yield Static("Epic Status", classes="section-header")
            self.progress_table = DataTable()
            self.progress_table.add_columns("Epic", "Progress", "Issues", "Status", "Activity")
            yield self.progress_table

            # Activity log
            yield Static("Recent Activity", classes="section-header")
            self.activity_log = Log(auto_scroll=True, max_lines=50)
            yield self.activity_log

    def update_epic_progress(
        self,
        epic_number: int,
        progress_data: Dict[str, Any]
    ) -> None:
        """Update progress information for an epic.

        Args:
            epic_number: Epic number to update
            progress_data: Dictionary containing progress information
        """
        # TODO: Implement epic progress updating
        # TODO: Parse progress_data into EpicProgress object
        # TODO: Update progress bars and displays
        # TODO: Log progress changes

        console.print(f"[blue]Updating progress for epic {epic_number}[/blue]")

        # Extract progress information
        total_issues = progress_data.get('total_issues', 0)
        completed_issues = progress_data.get('completed_issues', 0)
        in_progress_issues = progress_data.get('in_progress_issues', 0)
        blocked_issues = progress_data.get('blocked_issues', 0)

        completion_percentage = 0.0
        if total_issues > 0:
            completion_percentage = (completed_issues / total_issues) * 100

        progress = EpicProgress(
            epic_number=epic_number,
            title=progress_data.get('title', f'Epic {epic_number}'),
            total_issues=total_issues,
            completed_issues=completed_issues,
            in_progress_issues=in_progress_issues,
            blocked_issues=blocked_issues,
            completion_percentage=completion_percentage,
            estimated_completion=progress_data.get('estimated_completion'),
            last_activity=datetime.now().isoformat()
        )

        self.epic_progress[epic_number] = progress
        self._refresh_progress_display()

        # Log progress update
        self.log_activity(
            f"Epic {epic_number} progress updated: {completion_percentage:.1f}% complete",
            "success"
        )

    def _refresh_progress_display(self) -> None:
        """Refresh the progress display with current data."""
        if not self.progress_table:
            return

        # TODO: Implement progress table refreshing
        # TODO: Clear and rebuild table rows
        # TODO: Update progress bars and percentages
        # TODO: Apply status colors and formatting

        # Clear existing rows
        self.progress_table.clear()

        # Add updated progress data
        for epic_num, progress in self.epic_progress.items():
            status = self._get_epic_status_text(progress)
            progress_text = f"{progress.completion_percentage:.1f}%"
            issues_text = f"{progress.completed_issues}/{progress.total_issues}"
            activity_text = "Active" if progress.in_progress_issues > 0 else "Idle"

            self.progress_table.add_row(
                str(epic_num),
                progress_text,
                issues_text,
                status,
                activity_text
            )

        # Update summary
        self._update_summary_display()

    def _get_epic_status_text(self, progress: EpicProgress) -> str:
        """Get status text for an epic based on its progress.

        Args:
            progress: Epic progress information

        Returns:
            Status text with appropriate formatting
        """
        # TODO: Implement status determination logic
        # TODO: Consider blocked issues, completion rate, etc.
        # TODO: Return formatted status text

        if progress.blocked_issues > 0:
            return "🚫 Blocked"
        elif progress.completion_percentage >= 100:
            return "✅ Complete"
        elif progress.in_progress_issues > 0:
            return "📝 Active"
        elif progress.completion_percentage > 0:
            return "⏳ Started"
        else:
            return "⏸️ Pending"

    def _update_summary_display(self) -> None:
        """Update the summary display with aggregated statistics."""
        if not self.summary_display:
            return

        # TODO: Implement summary statistics calculation
        # TODO: Calculate totals across all epics
        # TODO: Show overall progress and health metrics

        total_epics = len(self.epic_progress)
        total_issues = sum(p.total_issues for p in self.epic_progress.values())
        completed_issues = sum(p.completed_issues for p in self.epic_progress.values())
        active_epics = sum(1 for p in self.epic_progress.values() if p.in_progress_issues > 0)

        overall_completion = 0.0
        if total_issues > 0:
            overall_completion = (completed_issues / total_issues) * 100

        summary_text = (
            f"Epics: {total_epics} total, {active_epics} active | "
            f"Issues: {completed_issues}/{total_issues} complete | "
            f"Overall: {overall_completion:.1f}%"
        )

        self.summary_display.update(summary_text)

    def log_activity(
        self,
        message: str,
        level: str = "info",
        epic_number: Optional[int] = None,
        issue_number: Optional[int] = None,
        event_type: str = "general",
        instance: Optional[str] = None
    ) -> None:
        """Log an activity event.

        Args:
            message: Activity message
            level: Log level (info, success, warning, error)
            epic_number: Optional epic number
            issue_number: Optional issue number
            event_type: Type of event
            instance: Optional instance name
        """
        # TODO: Implement activity logging
        # TODO: Format messages with colors and icons
        # TODO: Store in activity history
        # TODO: Limit history size

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Create activity event
        event = ActivityEvent(
            timestamp=timestamp,
            epic_number=epic_number,
            issue_number=issue_number,
            event_type=event_type,
            message=message,
            level=level,
            instance=instance
        )

        # Add to history
        self.activity_history.append(event)

        # Limit history size
        if len(self.activity_history) > self.max_activity_entries:
            self.activity_history = self.activity_history[-self.max_activity_entries:]

        # Format and display in log
        if self.activity_log:
            formatted_message = self._format_activity_message(event)
            self.activity_log.write(formatted_message)

    def _format_activity_message(self, event: ActivityEvent) -> Text:
        """Format an activity event for display.

        Args:
            event: Activity event to format

        Returns:
            Formatted Rich Text object
        """
        # TODO: Implement activity message formatting
        # TODO: Add timestamps, colors, and context
        # TODO: Include epic/issue information

        text = Text()

        # Add timestamp
        text.append(f"[{event.timestamp}] ", style="dim")

        # Add level-specific styling
        if event.level == "success":
            text.append("✓ ", style="green")
        elif event.level == "warning":
            text.append("⚠ ", style="yellow")
        elif event.level == "error":
            text.append("✗ ", style="red")
        else:
            text.append("• ", style="blue")

        # Add context information
        if event.epic_number:
            text.append(f"Epic {event.epic_number}: ", style="bold")

        if event.issue_number:
            text.append(f"#{event.issue_number} ", style="cyan")

        # Add main message
        message_style = {
            "success": "green",
            "warning": "yellow",
            "error": "red"
        }.get(event.level, "default")

        text.append(event.message, style=message_style)

        # Add instance information
        if event.instance:
            text.append(f" ({event.instance})", style="dim")

        return text

    def get_epic_statistics(self, epic_number: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific epic.

        Args:
            epic_number: Epic number

        Returns:
            Dictionary with detailed epic statistics
        """
        # TODO: Implement detailed statistics calculation
        # TODO: Include timing information, velocity metrics
        # TODO: Add trend analysis and predictions

        if epic_number not in self.epic_progress:
            return {}

        progress = self.epic_progress[epic_number]

        # Calculate additional metrics
        pending_issues = progress.total_issues - progress.completed_issues - progress.in_progress_issues
        velocity = self._calculate_velocity(epic_number)
        estimated_days_remaining = self._estimate_completion_days(epic_number)

        statistics = {
            'epic_number': epic_number,
            'title': progress.title,
            'total_issues': progress.total_issues,
            'completed_issues': progress.completed_issues,
            'in_progress_issues': progress.in_progress_issues,
            'pending_issues': pending_issues,
            'blocked_issues': progress.blocked_issues,
            'completion_percentage': progress.completion_percentage,
            'velocity_issues_per_day': velocity,
            'estimated_days_remaining': estimated_days_remaining,
            'last_activity': progress.last_activity
        }

        return statistics

    def _calculate_velocity(self, epic_number: int) -> float:
        """Calculate development velocity for an epic.

        Args:
            epic_number: Epic number

        Returns:
            Velocity in issues per day
        """
        # TODO: Implement velocity calculation
        # TODO: Track completion timestamps
        # TODO: Calculate moving average

        # Placeholder calculation
        return 1.5

    def _estimate_completion_days(self, epic_number: int) -> Optional[float]:
        """Estimate days until epic completion.

        Args:
            epic_number: Epic number

        Returns:
            Estimated days until completion, None if cannot estimate
        """
        # TODO: Implement completion estimation
        # TODO: Use velocity and remaining work
        # TODO: Account for blocked issues and dependencies

        if epic_number not in self.epic_progress:
            return None

        progress = self.epic_progress[epic_number]
        velocity = self._calculate_velocity(epic_number)

        if velocity > 0:
            remaining_issues = progress.total_issues - progress.completed_issues
            return remaining_issues / velocity

        return None

    def filter_activity(
        self,
        epic_number: Optional[int] = None,
        level: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> List[ActivityEvent]:
        """Filter activity events by criteria.

        Args:
            epic_number: Filter by epic number
            level: Filter by log level
            event_type: Filter by event type

        Returns:
            List of filtered activity events
        """
        # TODO: Implement activity filtering
        # TODO: Support multiple filter criteria
        # TODO: Return filtered results

        filtered_events = self.activity_history

        if epic_number is not None:
            filtered_events = [e for e in filtered_events if e.epic_number == epic_number]

        if level is not None:
            filtered_events = [e for e in filtered_events if e.level == level]

        if event_type is not None:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]

        return filtered_events

    def export_progress_report(self) -> Dict[str, Any]:
        """Export comprehensive progress report.

        Returns:
            Dictionary containing complete progress information
        """
        # TODO: Implement progress report generation
        # TODO: Include all epic statistics
        # TODO: Add activity summary and trends

        report = {
            'generated_at': datetime.now().isoformat(),
            'epic_progress': {
                epic_num: {
                    'epic_number': progress.epic_number,
                    'title': progress.title,
                    'total_issues': progress.total_issues,
                    'completed_issues': progress.completed_issues,
                    'in_progress_issues': progress.in_progress_issues,
                    'blocked_issues': progress.blocked_issues,
                    'completion_percentage': progress.completion_percentage,
                    'estimated_completion': progress.estimated_completion,
                    'last_activity': progress.last_activity
                }
                for epic_num, progress in self.epic_progress.items()
            },
            'activity_summary': {
                'total_events': len(self.activity_history),
                'events_by_level': {},
                'events_by_type': {}
            }
        }

        # Count events by level and type
        for event in self.activity_history:
            level_key = event.level
            report['activity_summary']['events_by_level'][level_key] = \
                report['activity_summary']['events_by_level'].get(level_key, 0) + 1

            type_key = event.event_type
            report['activity_summary']['events_by_type'][type_key] = \
                report['activity_summary']['events_by_type'].get(type_key, 0) + 1

        return report

    def clear_activity_history(self, older_than_hours: Optional[int] = None) -> int:
        """Clear activity history.

        Args:
            older_than_hours: Only clear events older than specified hours

        Returns:
            Number of events cleared
        """
        # TODO: Implement selective activity clearing
        # TODO: Support time-based filtering
        # TODO: Preserve recent activity

        if older_than_hours is None:
            # Clear all history
            cleared_count = len(self.activity_history)
            self.activity_history.clear()
        else:
            # Clear old events only
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
            cutoff_str = cutoff_time.strftime("%H:%M:%S")

            old_events = [e for e in self.activity_history if e.timestamp < cutoff_str]
            cleared_count = len(old_events)

            self.activity_history = [e for e in self.activity_history if e.timestamp >= cutoff_str]

        console.print(f"[blue]Cleared {cleared_count} activity events[/blue]")
        return cleared_count