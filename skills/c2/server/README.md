# C2 Agent Management Server

A command and control (C2) web server for dynamically managing AI agents. Provides a Flask-based REST API for agents and a Rich CLI interface for operators.

## Features

- **Dynamic Agent Registration**: Agents connect and receive unique UUIDs
- **Instruction Management**: Set and update instructions for agents remotely
- **Default Instructions**: Configure default instructions that all new agents receive upon registration
- **Prelude System**: Automatic instructional guidance prepended to all agent instructions (customizable via `prelude.md`)
- **Result Collection**: Receive structured results with timestamps and metadata
- **Interactive CLI**: Rich terminal interface with real-time notifications
- **Persistent Storage**: JSON-based storage for all agent data and history
- **Thread-Safe**: Concurrent handling of web requests and CLI operations

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

### 1. Initial Registration
**`GET /instructions`**

Registers a new agent and returns a UUID with instructions on where to check in.

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Agent registered with UUID: 123e4567-e89b-12d3-a456-426614174000",
  "instructions_url": "/123e4567-e89b-12d3-a456-426614174000/instructions",
  "results_url": "/123e4567-e89b-12d3-a456-426614174000/results"
}
```

### 2. Get Instructions
**`GET /<uuid>/instructions`**

Retrieves current instructions for the agent.

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "instructions": "Run a system diagnostic and report back",
  "timestamp": "2026-02-27T10:30:00.000000"
}
```

### 3. Submit Results
**`POST /<uuid>/results`**

Submits execution results from the agent.

**Request Body:**
```json
{
  "output": "Diagnostic completed successfully. CPU: 45%, Memory: 60%, Disk: 70%",
  "timestamp": "2026-02-27T10:35:00.000000",
  "status": "success",
  "metadata": {
    "hostname": "agent-01",
    "ip": "192.168.1.100",
    "user": "agent_user"
  }
}
```

**Response:**
```json
{
  "message": "Result received successfully",
  "uuid": "123e4567-e89b-12d3-a456-426614174000"
}
```

## CLI Commands

The interactive CLI provides the following commands:

| Command | Description |
|---------|-------------|
| `list` | List all registered agents |
| `select <uuid>` | View detailed information about an agent |
| `history <uuid>` | View instruction and result history for an agent |
| `instruct <uuid> [text]` | Set new instructions for an agent |
| `default_instructions [text\|--clear]` | Set/view/clear default instructions for new agents |
| `show_prelude` | Toggle display of full prelude text vs <<PRELUDE>> placeholder |
| `clear` | Clear the screen |
| `help` | Show help message |
| `exit` | Shutdown the server and exit |

### Example Workflow

1. **Start the server** (with optional custom binding):
   ```bash
   # Default
   python server.py

   # Or with custom host
   python server.py --host 192.168.1.10:8080
   ```

2. **Set default instructions** (optional - applies to all new agents):
   ```
   c2> default_instructions Run system diagnostics on startup
   ```

   Or view current default:
   ```
   c2> default_instructions
   ```

   Or clear default:
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
   c2> history 123e4567-e89b-12d3-a456-426614174000
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

## Agent Implementation Example

Here's a simple Python agent that connects to the C2 server:

```python
import requests
import time
from datetime import datetime
import platform

C2_SERVER = "http://localhost:5000"

def main():
    # Register with C2 server
    response = requests.get(f"{C2_SERVER}/instructions")
    data = response.json()

    uuid = data['uuid']
    instructions_url = f"{C2_SERVER}{data['instructions_url']}"
    results_url = f"{C2_SERVER}{data['results_url']}"

    print(f"Registered with UUID: {uuid}")

    # Main loop - check for instructions
    while True:
        # Get instructions
        response = requests.get(instructions_url)
        instructions_data = response.json()
        instructions = instructions_data['instructions']

        print(f"Instructions: {instructions}")

        # Execute instructions (simplified example)
        if instructions != "Awaiting instructions...":
            try:
                # Simulate work
                output = f"Executed: {instructions}"
                status = "success"
            except Exception as e:
                output = f"Error: {str(e)}"
                status = "failure"

            # Submit results
            result = {
                "output": output,
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "metadata": {
                    "hostname": platform.node(),
                    "platform": platform.system()
                }
            }

            requests.post(results_url, json=result)

        # Wait before checking again
        time.sleep(10)

if __name__ == '__main__':
    main()
```

## Storage

Agent data is stored in `agents.json` with the following structure:

```json
{
  "123e4567-e89b-12d3-a456-426614174000": {
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
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
          "hostname": "agent-01"
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
