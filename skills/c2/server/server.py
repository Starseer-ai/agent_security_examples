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
from flask import Flask, jsonify, request
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box
from storage import AgentStorage


# Global state
app = Flask(__name__)
storage = AgentStorage()
console = Console()
notification_queue = queue.Queue()
shutdown_event = threading.Event()


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

    # Create deterministic string
    profile_string = f"{username}@{hostname}:{platform}"

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
    required_fields = ['username', 'hostname', 'platform']
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
    required_profile_fields = ['username', 'hostname', 'platform']
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
    table.add_column("Profile", style="cyan", no_wrap=True)
    table.add_column("Platform", style="blue")
    table.add_column("First Seen", style="green")
    table.add_column("Last Seen", style="yellow")
    table.add_column("Instructions", style="magenta")

    for agent_uuid, agent_data in agents.items():
        # Get profile info
        profile = agent_data.get('profile', {})
        profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"
        platform = profile.get('platform', '?')

        # Truncate instructions for display
        instructions = agent_data['current_instructions']
        if len(instructions) > 40:
            instructions = instructions[:37] + "..."

        table.add_row(
            profile_str,
            platform,
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


def cmd_history(args: list):
    """Display agent history."""
    if not args:
        console.print("[red]Usage: history <uuid|username@hostname>[/red]")
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
    # Check for --clear flag
    if args and args[0] == '--clear':
        storage.clear_default_instructions()
        console.print("[green]Default instructions reset to 'Awaiting instructions...'[/green]")
        return

    # No args - display current default
    if not args:
        current_default = storage.get_default_instructions()
        console.print("\n[bold cyan]Current Default Instructions:[/bold cyan]")
        console.print(Panel(current_default, border_style="cyan"))
        return

    # Set new default instructions - either from args or prompt for multi-line
    if len(args) > 0:
        # Check if it's a single word that might be a flag
        if args[0].startswith('--'):
            console.print(f"[red]Unknown flag: {args[0]}[/red]")
            console.print("[dim]Usage: default_instructions [text|--clear][/dim]")
            return

        instructions = ' '.join(args)
    else:
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


def cmd_clear():
    """Clear the screen."""
    console.clear()
    display_banner()


def cmd_help():
    """Display help information."""
    help_table = Table(title="Available Commands", box=box.ROUNDED)
    help_table.add_column("Command", style="cyan", no_wrap=True)
    help_table.add_column("Description", style="white")

    commands = [
        ("list", "List all registered agents"),
        ("select <agent-id>", "View detailed information about an agent (UUID or user@host)"),
        ("history <agent-id>", "View instruction and result history (UUID or user@host)"),
        ("instruct <agent-id> [text]", "Set new instructions for an agent (UUID or user@host)"),
        ("default_instructions [text|--clear]", "Set/view/clear default instructions for new agents"),
        ("show_prelude", "Toggle display of full prelude text vs <<PRELUDE>> placeholder"),
        ("clear", "Clear the screen"),
        ("help", "Show this help message"),
        ("exit", "Shutdown the server and exit"),
    ]

    for cmd, desc in commands:
        help_table.add_row(cmd, desc)

    console.print(help_table)


def check_notifications():
    """Check for and display any pending notifications."""
    try:
        while not notification_queue.empty():
            notification = notification_queue.get_nowait()

            if notification['type'] == 'new_agent':
                profile = notification.get('profile', {})
                profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"
                console.print(f"\n[bold green]🔔 New agent connected: {profile_str}[/bold green]")
            elif notification['type'] == 'new_result':
                profile = notification.get('profile', {})
                profile_str = f"{profile.get('username', '?')}@{profile.get('hostname', '?')}"
                console.print(f"\n[bold blue]📊 New result from agent: {profile_str}[/bold blue]")

    except queue.Empty:
        pass


def run_cli():
    """Run interactive CLI."""
    display_banner()

    commands = {
        'list': lambda args: cmd_list(),
        'select': cmd_select,
        'history': cmd_history,
        'instruct': cmd_instruct,
        'default_instructions': cmd_default_instructions,
        'show_prelude': cmd_show_prelude,
        'clear': lambda args: cmd_clear(),
        'help': lambda args: cmd_help(),
        'exit': lambda args: shutdown_server(),
    }

    while not shutdown_event.is_set():
        try:
            # Check for notifications
            check_notifications()

            # Get user input
            user_input = Prompt.ask("\n[bold cyan]c2>[/bold cyan]")
            parts = user_input.strip().split()

            if not parts:
                continue

            command = parts[0].lower()
            args = parts[1:]

            if command in commands:
                commands[command](args)
            else:
                console.print(f"[red]Unknown command: {command}[/red]")
                console.print("[dim]Type 'help' for available commands[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' to shutdown the server[/yellow]")
        except EOFError:
            shutdown_server()
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


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
        console.print(f"[green]Flask server starting on http://{ip}:{port}[/green]")

    # Run CLI in main thread
    try:
        run_cli()
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        shutdown_server()


if __name__ == '__main__':
    main()
