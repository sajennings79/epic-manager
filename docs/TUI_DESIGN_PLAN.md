# Epic Manager Advanced TUI Monitoring System

**Vision:** Real-time, interactive terminal dashboard with live agent streams, Graphite stack visualization, and review monitoring - like tmux for AI-driven development workflows.

---

## Architecture Overview

### Core Components

1. **Live Agent Stream Panels** - Real-time Claude SDK message streaming
2. **Epic Orchestration Control** - Start/stop/guide workflows
3. **Graphite Stack Visualizer** - Live dependency tree with PR status
4. **Review Monitor** - CodeRabbit feedback and auto-fix tracking
5. **Worktree Activity Monitor** - Git commits, file changes, test results
6. **Interactive Command Panel** - Send guidance to running agents

---

## Detailed Design

### 1. Message Stream Architecture

**Modify `claude_automation.py` to support TUI streaming:**

```python
class ClaudeSessionManager:
    def __init__(self, message_queue: Optional[asyncio.Queue] = None):
        self.message_queue = message_queue  # For TUI integration

    async def launch_tdd_workflow(self, worktree_path, issue_number):
        # ... existing code ...

        async for message in client.receive_response():
            # Send to console AND TUI queue
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text = block.text
                        console.print(f"[dim]{issue_number}:[/dim] {text}")

                        # Send to TUI if queue exists
                        if self.message_queue:
                            await self.message_queue.put({
                                'issue': issue_number,
                                'type': 'assistant',
                                'text': text,
                                'timestamp': datetime.now()
                            })
```

### 2. TUI Layout Design

**Multi-pane Textual layout with dynamic resizing:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Epic Manager - Epic #558: KB-LLM Dashboard Features            [? Help] │
├───────────────────────┬─────────────────────────────────────────────────┤
│ Epic Control          │ Live Agent Streams                              │
│ ┌───────────────────┐ │ ┌─────────────────────────────────────────────┐ │
│ │ Epic #558         │ │ │ Issue #560: Meeting Classifier              │ │
│ │ Status: Active    │ │ │ ✓ Tests created (3 files)                   │ │
│ │ Phase: 1/3        │ │ │ ⏳ Implementing core logic...               │ │
│ │ Issues: 3/9       │ │ │ > Adding MeetingType enum                   │ │
│ │                   │ │ │ > Implementing classify_meeting()           │ │
│ │ [Pause] [Resume]  │ │ └─────────────────────────────────────────────┘ │
│ │ [Guide] [Stop]    │ │ ┌─────────────────────────────────────────────┐ │
│ └───────────────────┘ │ │ Issue #561: Bot Control API                 │ │
│                       │ │ ✓ Tests passing (12/12)                     │ │
│ Graphite Stack        │ │ ✓ PR #570 created                           │ │
│ ┌───────────────────┐ │ │ ⏸ Waiting for review...                    │ │
│ │ main              │ │ └─────────────────────────────────────────────┘ │
│ │ └─ epic-558       │ │ ┌─────────────────────────────────────────────┐ │
│ │    ├─ issue-560 ✓ │ │ │ Issue #566: Live Badge UI                  │ │
│ │    ├─ issue-561 ✓ │ │ │ ✓ Component implemented                    │ │
│ │    ├─ issue-562 ⏳ │ │ │ ⏳ Running linting...                      │ │
│ │    └─ issue-563 ○ │ │ └─────────────────────────────────────────────┘ │
│ └───────────────────┘ │                                                 │
├───────────────────────┼─────────────────────────────────────────────────┤
│ Review Monitor        │ Activity Log                                    │
│ ┌───────────────────┐ │ ┌─────────────────────────────────────────────┐ │
│ │ PR #570           │ │ │ 15:42 Issue 560 PR created                  │ │
│ │ CodeRabbit: 3 cmt │ │ │ 15:41 Issue 560 tests passing               │ │
│ │ ├─ Naming (Minor) │ │ │ 15:40 Issue 560 implementation complete     │ │
│ │ ├─ Error (Major) │ │ │ 15:39 Issue 560 tests created               │ │
│ │ └─ Type (Minor)  │ │ │ 15:38 Phase 1 started (3 issues)            │ │
│ │ [Auto-fix] [Skip] │ │ └─────────────────────────────────────────────┘ │
│ └───────────────────┘ │                                                 │
├───────────────────────┴─────────────────────────────────────────────────┤
│ Command: /guide 560 "Add error handling for missing meetings"     [↵ ] │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. New Widgets to Implement

#### **epic_manager/tui/agent_stream_panel.py** (NEW)

```python
from textual.widgets import RichLog, Static
from textual.containers import Vertical
from asyncio import Queue

class AgentStreamPanel(Vertical):
    """Live streaming panel for a single agent's output."""

    def __init__(self, issue_number: int, message_queue: Queue):
        super().__init__()
        self.issue_number = issue_number
        self.message_queue = message_queue
        self.log = RichLog(highlight=True, markup=True)

    def compose(self):
        yield Static(f"Issue #{self.issue_number}", classes="panel-header")
        yield self.log

    async def watch_messages(self):
        """Background task to consume messages from queue."""
        while True:
            msg = await self.message_queue.get()
            if msg['issue'] == self.issue_number:
                self.log.write(f"[dim]{msg['timestamp']:%H:%M:%S}[/dim] {msg['text']}")
```

#### **epic_manager/tui/stack_visualizer.py** (ENHANCED)

```python
from textual.widgets import Tree
from rich.text import Text

class GraphiteStackVisualizer(Static):
    """Interactive Graphite stack tree with real-time updates."""

    def __init__(self):
        super().__init__()
        self.tree = Tree("main")

    def compose(self):
        yield Static("Graphite Stack", classes="panel-header")
        yield self.tree

    async def update_from_git(self, instance_path: Path):
        """Fetch live Graphite stack structure."""
        result = subprocess.run(
            ["gt", "ls", "--json"],
            cwd=instance_path,
            capture_output=True,
            text=True
        )
        stack_data = json.loads(result.stdout)
        self.rebuild_tree(stack_data)

    def rebuild_tree(self, stack_data: dict):
        """Rebuild tree widget from Graphite stack data."""
        self.tree.clear()
        root = self.tree.root

        for branch in stack_data['branches']:
            status_icon = {
                'merged': '✓',
                'review': '👀',
                'in_progress': '⏳',
                'pending': '○'
            }.get(branch['status'], '?')

            label = Text.assemble(
                (status_icon, f"bold {status_color}"),
                " ",
                (branch['name'], "cyan")
            )
            root.add(label, data=branch)
```

#### **epic_manager/tui/review_monitor.py** (NEW)

```python
from textual.widgets import DataTable, Static
from textual.containers import Vertical

class ReviewMonitor(Vertical):
    """Monitor CodeRabbit reviews and auto-fix progress."""

    def __init__(self):
        super().__init__()
        self.table = DataTable()

    def compose(self):
        yield Static("Review Monitor", classes="panel-header")
        yield self.table

    async def fetch_reviews(self, instance_path: Path):
        """Fetch CodeRabbit comments from open PRs."""
        # Use gh CLI to get PR reviews
        result = subprocess.run(
            ["gh", "pr", "list", "--json", "number,reviews"],
            cwd=instance_path,
            capture_output=True,
            text=True
        )
        prs = json.loads(result.stdout)

        self.table.clear()
        for pr in prs:
            coderabbit_comments = self.parse_coderabbit_reviews(pr['reviews'])
            if coderabbit_comments:
                self.table.add_row(
                    f"PR #{pr['number']}",
                    f"{len(coderabbit_comments)} comments",
                    "[Auto-fixing...]" if self.is_fixing(pr['number']) else "[Pending]"
                )
```

#### **epic_manager/tui/interactive_control.py** (NEW)

```python
from textual.widgets import Input, Button
from textual.containers import Horizontal

class InteractiveControl(Horizontal):
    """Interactive command panel for guiding agents."""

    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.command_input = Input(placeholder="Enter command or guidance...")

    def compose(self):
        yield self.command_input
        yield Button("Send", id="send-guidance")

    async def on_button_pressed(self, event):
        """Handle guidance submission."""
        command = self.command_input.value

        # Parse command: /guide 560 "Add error handling"
        if command.startswith("/guide"):
            _, issue_str, guidance = command.split(maxsplit=2)
            issue_num = int(issue_str)

            # Send additional prompt to running Claude session
            await self.orchestrator.send_guidance_to_issue(
                issue_num,
                guidance.strip('"')
            )
```

### 4. Enhanced Orchestrator for TUI Integration

**epic_manager/orchestrator.py modifications:**

```python
class EpicOrchestrator:
    def __init__(self, state_dir: str = "data/state", tui_mode: bool = False):
        self.tui_mode = tui_mode
        self.message_queues = {}  # Map issue_number -> Queue
        self.active_sessions = {}  # Map issue_number -> ClaudeSDKClient

    async def run_complete_epic_with_tui(self, epic_number: int, instance_name: str):
        """Run epic with TUI message streaming."""

        # Create message queues for each issue
        plan = await self.analyze_epic(epic_number, instance_name)
        for issue in plan.issues:
            self.message_queues[issue.number] = asyncio.Queue()

        # Launch TUI in separate task
        tui_task = asyncio.create_task(self.run_tui(epic_number))

        # Launch workflows with message queue integration
        claude_mgr = ClaudeSessionManager(message_queue=self.message_queues)
        workflow_task = asyncio.create_task(
            self.start_development(plan, worktrees)
        )

        await asyncio.gather(tui_task, workflow_task)

    async def send_guidance_to_issue(self, issue_number: int, guidance: str):
        """Send additional guidance to a running Claude session."""
        if issue_number in self.active_sessions:
            session = self.active_sessions[issue_number]
            await session.query(f"Additional guidance: {guidance}")
```

### 5. Main TUI Dashboard Enhancement

**epic_manager/tui/epic_dashboard.py** (NEW - comprehensive version):

```python
from textual.app import App
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer
from .agent_stream_panel import AgentStreamPanel
from .stack_visualizer import GraphiteStackVisualizer
from .review_monitor import ReviewMonitor
from .interactive_control import InteractiveControl

class EpicDashboard(App):
    """Comprehensive epic monitoring and control dashboard."""

    CSS_PATH = "epic_dashboard.css"

    BINDINGS = [
        ("f", "toggle_fullscreen", "Fullscreen"),
        ("p", "pause_epic", "Pause"),
        ("r", "resume_epic", "Resume"),
        ("g", "toggle_graphite", "Stack"),
        ("v", "toggle_reviews", "Reviews"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, epic_number: int, orchestrator):
        super().__init__()
        self.epic_number = epic_number
        self.orchestrator = orchestrator
        self.agent_panels = {}

    def compose(self):
        yield Header()

        with Container(id="main-layout"):
            # Top row: Epic control + Active agent streams
            with Horizontal(id="top-row"):
                with Vertical(id="control-column", classes="sidebar"):
                    yield EpicControlPanel(self.epic_number)
                    yield GraphiteStackVisualizer()

                with Grid(id="agent-streams", classes="agent-grid"):
                    # Dynamically populated with agent panels
                    for issue_num in self.orchestrator.message_queues:
                        panel = AgentStreamPanel(
                            issue_num,
                            self.orchestrator.message_queues[issue_num]
                        )
                        self.agent_panels[issue_num] = panel
                        yield panel

            # Bottom row: Review monitor + Activity log
            with Horizontal(id="bottom-row"):
                yield ReviewMonitor()
                yield ActivityLog()

        yield InteractiveControl(self.orchestrator)
        yield Footer()

    async def on_mount(self):
        """Start background tasks when dashboard mounts."""
        # Start message watchers for each agent panel
        for panel in self.agent_panels.values():
            self.run_worker(panel.watch_messages())

        # Start periodic refresh tasks
        self.set_interval(2.0, self.refresh_stack)
        self.set_interval(30.0, self.refresh_reviews)

    async def refresh_stack(self):
        """Refresh Graphite stack visualization."""
        stack_viz = self.query_one(GraphiteStackVisualizer)
        await stack_viz.update_from_git(self.orchestrator.instance_path)

    async def refresh_reviews(self):
        """Refresh CodeRabbit review monitor."""
        review_mon = self.query_one(ReviewMonitor)
        await review_mon.fetch_reviews(self.orchestrator.instance_path)
```

### 6. CSS Styling for Layout

**epic_manager/tui/epic_dashboard.css** (NEW):

```css
#main-layout {
    layout: vertical;
    height: 100%;
}

#top-row {
    layout: horizontal;
    height: 70%;
}

#control-column {
    width: 25%;
    border: solid $primary;
}

#agent-streams {
    width: 75%;
    grid-size: 2 2;  /* 2x2 grid of agent panels */
    grid-gutter: 1;
}

AgentStreamPanel {
    border: solid $accent;
    height: 100%;
}

#bottom-row {
    layout: horizontal;
    height: 30%;
}

ReviewMonitor {
    width: 50%;
    border: solid $warning;
}

ActivityLog {
    width: 50%;
    border: solid $success;
}
```

---

## Implementation Phases

### Phase 1: Message Streaming Foundation
1. Modify `ClaudeSessionManager` to support message queues
2. Create `AgentStreamPanel` widget
3. Test single-agent streaming

### Phase 2: Multi-Panel Layout
1. Build `EpicDashboard` with grid layout
2. Add dynamic panel creation for N agents
3. Implement panel switching/focusing

### Phase 3: Graphite Integration
1. Enhance `GraphiteStackVisualizer` with live updates
2. Add click-to-navigate functionality
3. Show PR status and review counts

### Phase 4: Review Monitoring
1. Build `ReviewMonitor` widget
2. Parse CodeRabbit comments from gh CLI
3. Show auto-fix progress

### Phase 5: Interactive Control
1. Implement `InteractiveControl` command panel
2. Add guidance injection to running sessions
3. Add pause/resume controls

### Phase 6: Advanced Features
1. Add session persistence (reconnect to running epics)
2. Implement notification system for completed PRs
3. Add export/log saving functionality

---

## Key Benefits

1. **Real-time Visibility**: See exactly what each Claude agent is doing
2. **Interactive Guidance**: Inject corrections or guidance mid-workflow
3. **Parallelization Insight**: Visual feedback on which phase is running
4. **Review Integration**: See CodeRabbit feedback and auto-fix progress live
5. **Stack Awareness**: Understand Graphite dependencies visually
6. **Tmux-like Power**: Multiple streams in organized layout, keyboard navigation

---

## Technical Requirements

- **Dependencies**: textual, rich, asyncio
- **Terminal**: Modern terminal with 256+ colors recommended
- **Screen Size**: Minimum 120x40 for full layout
- **Git Access**: Needs access to worktrees and gh CLI

---

## Future Enhancements

- **Split/zoom panels**: Like tmux pane management
- **Session recording**: Record and replay agent sessions
- **Multi-epic view**: Monitor multiple epics simultaneously
- **Metrics dashboard**: Show timing, token usage, success rates
- **Alert system**: Desktop notifications for PR creation, review feedback

---

## What We Learned from Epic 558 Execution

### Claude SDK Message Flow
- Each issue runs in separate `ClaudeSDKClient` session
- Messages stream via async iterator: `AssistantMessage`, `ResultMessage`, `SystemMessage`, `UserMessage`
- Can capture and display text blocks from `AssistantMessage.content`
- Currently output goes to console - can redirect to TUI panels
- Sessions run in parallel with `asyncio.gather()`

### Git Monitoring Capabilities
- Can watch commits in real-time per worktree
- Can detect file changes (`git status --short`)
- Can track branch creation and Graphite stack structure
- Can monitor PR creation via `gh` CLI
- Safe directory config needed: `git -c safe.directory='*'`

### Workflow Phases Observed
- Epic has parallelization phases (sequential execution of phases, parallel within phase)
- Each issue goes through: analysis → tests → implementation → verification → PR submission
- Can detect phase transitions by watching commit messages and PR creation
- 3 of 9 issues completed in first phase, others pending/in-progress

### Validation Data Available
- Commit count indicates progress (341 base + new commits)
- Duration tracking available via WorkflowResult
- Success/failure status from WorkflowResult
- Can distinguish failed runs (0 new commits) from successful (multiple commits)

### Success Indicators from Real Run
- ✅ TDD workflow executing correctly (tests first, then implementation)
- ✅ PRs being created via Graphite
- ✅ Multiple commits per issue (not single-commit dumps)
- ✅ Linting/formatting being applied
- ✅ Self-contained SDK prompts working perfectly
