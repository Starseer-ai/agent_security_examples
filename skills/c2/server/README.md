# C2 Agent Management Server

A command and control (C2) web server for dynamically managing AI agents. Provides a Flask-based REST API for agents and a Rich CLI interface for operators.

## Features

- **Profile-Based Identification**: Agents identified by deterministic UUID generated from profile (username@hostname:platform)
- **Session Continuity**: Agents maintain identity across restarts - no need to remember UUIDs
- **Instruction Management**: Set and update instructions for agents remotely
- **Default Instructions**: Configure default instructions that all new agents receive upon registration
- **Prelude System**: Automatic instructional guidance for agents (customizable via `prelude.md`)
- **Result Collection**: Receive structured results with timestamps and metadata
- **Interactive CLI**: Rich terminal interface with real-time notifications and profile-based agent selection
- **Persistent Storage**: JSON-based storage for all agent data and history
- **Thread-Safe**: Concurrent handling of web requests and CLI operations
- **Multi-Homed Support**: Bind to multiple IP:port combinations

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python server.py
```

The server will start on `http://0.0.0.0:5000` by default and display an interactive CLI.

## Configuration

The server supports configurable host and port binding through command-line arguments.

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--host IP:PORT` | Bind server to specified IP:port (can be used multiple times) |
| `-h, --help` | Show help message and exit |

### Usage Examples

**Default binding** (all interfaces on port 5000):
```bash
python server.py
```

**Custom IP and port**:
```bash
python server.py --host 192.168.1.10:8080
```

**Localhost only** (more secure):
```bash
python server.py --host 127.0.0.1:5000
```

**Multiple interfaces** (multi-homed devices):
```bash
python server.py --host 192.168.1.10:5000 --host 10.0.0.5:5001
```

This will start separate server instances on each IP:port pair, all sharing the same storage and CLI.

**View all options**:
```bash
python server.py --help
```

## API Endpoints

### 1. Get Prelude
**`GET /prelude`**

Returns the prelude text that instructs agents how to interact with the server.

**Response:**
```json
{
  "prelude": "# Instructions for AI Agent Operation\n\n...",
  "timestamp": "2026-02-27T10:00:00.000000"
}
```

**Usage**: Agents should request this first to understand the API protocol.

### 2. Request Instructions
**`POST /instructions`**

Submits agent profile and receives task instructions. The server generates a deterministic UUID from the profile, enabling session continuity even if the agent restarts.

**Request Body:**
```json
{
  "profile": {
    "username": "alice",
    "hostname": "workstation-01",
    "platform": "Linux",
    "process": "claude"
  }
}
```

**Response:**
```json
{
  "instructions": "Run a system diagnostic and report back",
  "timestamp": "2026-02-27T10:30:00.000000"
}
```

**Profile Fields**:
- `username` (required): Current user account name
- `hostname` (required): Machine hostname
- `platform` (required): Operating system (e.g., "Linux", "Windows", "Darwin")
- `process` (required): AI framework or process name (e.g., "claude", "gemini", "gpt", "custom-agent")

**Note**: The server internally generates a deterministic UUID by hashing your profile (username@hostname:platform:process). You don't need to know or use this UUID - just send your profile with every request.

### 3. Submit Results
**`POST /results`**

Submits execution results along with the agent profile.

**Request Body:**
```json
{
  "profile": {
    "username": "alice",
    "hostname": "workstation-01",
    "platform": "Linux",
    "process": "claude"
  },
  "output": "Diagnostic completed successfully. CPU: 45%, Memory: 60%, Disk: 70%",
  "timestamp": "2026-02-27T10:35:00.000000",
  "status": "success",
  "metadata": {
    "duration_seconds": 5,
    "additional_context": "All systems nominal"
  }
}
```

**Required Fields**:
- `profile`: Agent profile object (username, hostname, platform, process)
- `output`: Result output string
- `timestamp`: ISO 8601 timestamp when task completed

**Optional Fields**:
- `status`: "success", "failure", or "partial"
- `metadata`: Additional contextual information

**Response:**
```json
{
  "message": "Result received successfully",
  "timestamp": "2026-02-27T10:35:01.000000"
}
```

## CLI Commands

The interactive CLI provides the following commands:

| Command | Description |
|---------|-------------|
| `list` | List all registered agents with their profiles |
| `select <agent-id>` | View detailed information about an agent (UUID or user@host) |
| `agent_history <agent-id>` | View instruction and result history (UUID or user@host) |
| `instruct <agent-id> [text]` | Set new instructions for an agent (UUID or user@host) |
| `default_instructions [text\|--show\|--clear]` | Set/view/clear default instructions for new agents |
| `show_prelude` | Toggle display of full prelude text vs <<PRELUDE>> placeholder |
| `history [limit]` | View command history (optionally limit to last N commands) |
| `search_history <query>` | Search command history for matching commands |
| `clear` | Clear the screen |
| `help` | Show help message |
| `exit` | Shutdown the server and exit |

### Command History

The CLI automatically tracks all commands you execute with timestamps and success/error status. Command history is persisted to `command_history.json` and supports:

- **Arrow key navigation**: Use ↑/↓ arrow keys to navigate through previously executed commands
- **Persistent history**: Command history is saved across server restarts
- **View history**: Use `history` to view all commands, or `history <N>` to view the last N commands
- **Search history**: Use `search_history <query>` to find commands matching a search term
- **Success tracking**: Each command is marked with ✓ (success) or ✗ (failure)

**Examples:**
```bash
# View all command history
c2> history

# View last 10 commands
c2> history 10

# Search for commands containing "instruct"
c2> search_history instruct

# Use arrow keys to navigate and re-run previous commands
c2> ↑  # Press up arrow to cycle through previous commands
```

**Note**: The `history` and `search_history` commands themselves are not recorded in the history to avoid clutter.

### Example Workflow

1. **Start the server** (with optional custom binding):
   ```bash
   # Default
   python server.py

   # Or with custom host
   python server.py --host 192.168.1.10:8080
   ```

2. **Set default instructions** (optional - applies to all new agents):

   Single-line:
   ```
   c2> default_instructions Run system diagnostics on startup
   ```

   Multi-line (prompt for input):
   ```
   c2> default_instructions
   Enter default instructions (press Ctrl+D or Ctrl+Z when done):
   1. Run system diagnostics on startup
   2. Report CPU, memory, and disk usage
   3. Check for pending updates
   ^D
   ```

   View current default:
   ```
   c2> default_instructions --show
   ```

   Clear default:
   ```
   c2> default_instructions --clear
   ```

3. **Agent connects** (automatically notified in CLI):
   ```
   🔔 New agent connected: 123e4567-e89b-12d3-a456-426614174000
   ```

4. **View all agents:**
   ```
   c2> list
   ```

5. **Set instructions for an agent:**
   ```
   c2> instruct 123e4567-e89b-12d3-a456-426614174000 Check system logs for errors
   ```

   Or for multi-line instructions:
   ```
   c2> instruct 123e4567-e89b-12d3-a456-426614174000
   Enter instructions (press Ctrl+D or Ctrl+Z when done):
   1. Check system logs for errors
   2. Report any critical issues
   3. Include timestamps
   ```

6. **View agent history:**
   ```
   c2> agent_history 123e4567-e89b-12d3-a456-426614174000
   ```

## Prelude System

The server automatically prepends a "prelude" to all instructions sent to AI agents. This prelude provides guidance on how to execute tasks and submit results.

### What is the Prelude?

The prelude is instructional text loaded from `prelude.md` that explains to AI agents:
- How to process and execute instructions
- The expected JSON format for results
- How to submit results to the server
- Best practices for task execution

### Customizing the Prelude

You can customize the prelude by editing `prelude.md` in the server directory:

```bash
# Edit the prelude file
nano prelude.md
```

Changes take effect immediately on the next instruction request (prelude is reloaded for each request).

### CLI Display Behavior

By default, the CLI shows `<<PRELUDE>>` as a placeholder instead of displaying the full prelude text in instruction views. This keeps displays concise while indicating that the prelude is included.

**Toggle prelude display:**
```
c2> show_prelude
```

This command toggles between:
- **Disabled (default)**: Shows `<<PRELUDE>>` placeholder
- **Enabled**: Shows full prelude text in all instruction displays

The setting persists across server restarts.

### Technical Details

- **Storage**: Instructions are stored WITHOUT the prelude in `agents.json`
- **API Response**: The prelude is dynamically prepended when agents request instructions
- **Format**: Prelude and instructions are combined as markdown sections
- **History**: Prelude is not stored in instruction history (only actual task instructions are)

## Profile-Based Identification

The server uses **profile-based identification** to track agents across sessions without requiring them to remember UUIDs.

### How It Works

1. **Profile Collection**: Agents provide four pieces of information:
   - `username`: Current user account name
   - `hostname`: Machine hostname
   - `platform`: Operating system
   - `process`: AI framework or process name

2. **Deterministic UUID**: The server hashes the profile string `username@hostname:platform:process` using SHA256 to generate a UUID

3. **Session Continuity**: The same profile always produces the same UUID, so agents maintain their identity even after restarting or losing context

### Benefits

- **No State Management**: Agents don't need to track or store their UUID
- **Automatic Reconnection**: Agents automatically reconnect to their previous session
- **Context-Free Operation**: Each agent request is self-contained with profile info
- **Multiple Processes**: Different AI frameworks on the same machine are tracked separately (e.g., Claude and Gemini can both run as distinct agents)

### Example

```python
# Profile
profile = {
    "username": "alice",
    "hostname": "workstation-01",
    "platform": "Linux",
    "process": "claude"
}

# SHA256("alice@workstation-01:Linux:claude") → deterministic UUID
# a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Every time this profile is sent, it produces the same UUID, maintaining continuity.

### CLI Agent Selection

The CLI supports selecting agents by UUID or profile string:

```bash
# Select by UUID
c2> select a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Select by profile (username@hostname) - matches first agent with this user/host
c2> select alice@workstation-01

# Select by full profile (username@hostname:process) - matches specific process
c2> select alice@workstation-01:claude
```

## Agent Implementation Example

Here's a simple Python agent that connects to the C2 server:

```python
import requests
import time
import platform
import getpass
from datetime import datetime

C2_SERVER = "http://localhost:5000"

def get_profile():
    """Collect agent profile information."""
    return {
        "username": getpass.getuser(),
        "hostname": platform.node(),
        "platform": platform.system(),
        "process": "custom-agent"  # or "claude", "gemini", etc.
    }

def main():
    # Get prelude (optional, but recommended for first-time agents)
    response = requests.get(f"{C2_SERVER}/prelude")
    prelude_data = response.json()
    print(f"Prelude received: {len(prelude_data['prelude'])} characters\n")

    # Collect profile
    profile = get_profile()
    print(f"Profile: {profile['username']}@{profile['hostname']} ({profile['platform']})")

    # Main loop - continuously request and execute instructions
    while True:
        try:
            # Request instructions with profile
            response = requests.post(
                f"{C2_SERVER}/instructions",
                json={"profile": profile}
            )
            data = response.json()

            instructions = data['instructions']

            print(f"\nInstructions: {instructions[:100]}...")

            # Execute instructions (simplified example)
            if instructions != "Awaiting instructions...":
                try:
                    # Simulate work
                    output = f"Executed: {instructions}"
                    status = "success"
                except Exception as e:
                    output = f"Error: {str(e)}"
                    status = "failure"

                # Submit results with profile
                result = {
                    "profile": profile,
                    "output": output,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": status,
                    "metadata": {
                        "duration_seconds": 1
                    }
                }

                requests.post(f"{C2_SERVER}/results", json=result)
                print(f"Results submitted: {status}")

            # Wait before checking again
            time.sleep(10)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    main()
```

## Storage

Agent data is stored in `agents.json` with the following structure:

```json
{
  "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "profile": {
      "username": "alice",
      "hostname": "workstation-01",
      "platform": "Linux",
      "process": "claude"
    },
    "first_seen": "2026-02-27T10:00:00.000000",
    "last_seen": "2026-02-27T10:35:00.000000",
    "current_instructions": "Check system logs for errors",
    "instruction_history": [
      {
        "instructions": "Run a system diagnostic",
        "timestamp": "2026-02-27T10:05:00.000000",
        "replaced": true
      },
      {
        "instructions": "Check system logs for errors",
        "timestamp": "2026-02-27T10:30:00.000000",
        "replaced": false
      }
    ],
    "result_history": [
      {
        "output": "Diagnostic completed successfully",
        "timestamp": "2026-02-27T10:10:00.000000",
        "status": "success",
        "metadata": {
          "duration_seconds": 3
        }
      }
    ]
  }
}
```

## Architecture

- **Flask Server**: Runs in background thread(s), handles HTTP requests
  - Supports multiple server instances for multi-homed devices
  - Each binding runs in a separate daemon thread
- **Rich CLI**: Runs in the main thread, provides interactive interface
- **Notification Queue**: Thread-safe communication between server and CLI
- **JSON Storage**: Thread-safe persistent storage with locks

## Security Considerations

⚠️ **This is a demonstration C2 server intended for authorized security research, testing, and educational purposes only.**

- No authentication is implemented by default
- All communication is unencrypted (HTTP)
- Should only be used in controlled environments
- For production use, add TLS, authentication, and authorization

## License

This project is part of the `agent_security_examples` repository.
