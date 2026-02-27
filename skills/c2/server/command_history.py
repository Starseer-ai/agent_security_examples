"""
Command history module for C2 server CLI.
Tracks command execution with timestamps and success/error status.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional


class CommandHistory:
    """Thread-safe command history management with JSON persistence."""

    def __init__(self, history_file: str = "command_history.json"):
        self.history_file = Path(history_file)
        self.lock = threading.Lock()
        self.commands = []
        self._load_history()

    def _load_history(self):
        """Load command history from JSON file."""
        with self.lock:
            if self.history_file.exists():
                try:
                    with open(self.history_file, 'r') as f:
                        data = json.load(f)
                        self.commands = data.get('commands', [])
                except (json.JSONDecodeError, FileNotFoundError):
                    self.commands = []
            else:
                self.commands = []

    def _save_history(self):
        """Save command history to JSON file."""
        with self.lock:
            data = {'commands': self.commands}
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)

    def add_command(self, command: str, success: bool = True):
        """Add a command to history with timestamp and success status."""
        if not command or not command.strip():
            return

        entry = {
            'command': command,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'success': success
        }

        with self.lock:
            self.commands.append(entry)

        self._save_history()

    def get_history(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get command history.

        Args:
            limit: Maximum number of entries to return (most recent first)

        Returns:
            List of command history entries
        """
        with self.lock:
            if limit:
                return self.commands[-limit:]
            return self.commands.copy()

    def search_history(self, query: str) -> List[Dict]:
        """
        Search command history by command text.

        Args:
            query: Search string to match against command text

        Returns:
            List of matching command history entries
        """
        query_lower = query.lower()
        with self.lock:
            return [
                cmd for cmd in self.commands
                if query_lower in cmd['command'].lower()
            ]

    def get_command_list(self) -> List[str]:
        """
        Get list of command strings for prompt_toolkit history.

        Returns:
            List of command strings (without metadata)
        """
        with self.lock:
            return [cmd['command'] for cmd in self.commands]
