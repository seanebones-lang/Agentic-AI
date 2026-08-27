"""Shell command execution tool for running system commands."""

from typing import Any, Dict, List, Optional
import subprocess
import shlex
import os

from tools.tool_manager import BaseTool


class ShellTool(BaseTool):
    """Tool for executing shell commands in a controlled environment."""

    def __init__(
        self,
        allowed_commands: Optional[List[str]] = None,
        blocked_commands: Optional[List[str]] = None,
        working_directory: Optional[str] = None,
        max_execution_time: int = 60,
        allow_pipes: bool = False,
        allow_redirects: bool = False,
    ) -> None:
        """
        Initialize shell tool.

        Args:
            allowed_commands: List of allowed command names (None = allow all except blocked)
            blocked_commands: List of blocked command names
            working_directory: Working directory for commands
            max_execution_time: Maximum execution time in seconds
            allow_pipes: Allow pipe operators (|)
            allow_redirects: Allow redirect operators (>, >>, <)
        """
        super().__init__(
            name="shell",
            description="Execute shell commands in a controlled environment. Supports command allowlist/blocklist, working directory, and timeout.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Execution timeout in seconds",
                        "default": 30,
                    },
                    "env": {
                        "type": "object",
                        "description": "Environment variables to set",
                    },
                    "capture_output": {
                        "type": "boolean",
                        "description": "Capture stdout/stderr",
                        "default": True,
                    },
                },
                "required": ["command"],
            },
            returns={
                "type": "object",
                "properties": {
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "return_code": {"type": "integer"},
                    "success": {"type": "boolean"},
                    "execution_time": {"type": "number"},
                },
            },
            category="system",
            tags=["shell", "command", "system", "cli", "execution"],
            timeout=max_execution_time,
        )
        self.allowed_commands = set(allowed_commands) if allowed_commands else None
        self.blocked_commands = set(blocked_commands) if blocked_commands else {
            "rm", "rmdir", "del", "format", "fdisk", "mkfs",
            "dd", "shutdown", "reboot", "halt", "poweroff",
            "kill", "killall", "pkill", "init", "systemctl",
            "service", "mount", "umount", "chmod", "chown",
            "passwd", "useradd", "userdel", "groupadd", "groupdel",
            "su", "sudo", "doas", "visudo", "crontab", "at",
            "iptables", "firewall-cmd", "ufw", "netstat", "ss",
            "nc", "ncat", "socat", "openssl", "ssh", "scp",
            "rsync", "wget", "curl", "ftp", "sftp", "tftp",
        }
        self.working_directory = working_directory or os.getcwd()
        self.max_execution_time = max_execution_time
        self.allow_pipes = allow_pipes
        self.allow_redirects = allow_redirects

    def _validate_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Validate command against allowlist/blocklist."""
        # Check for dangerous patterns
        if not self.allow_pipes and "|" in command:
            return False, "Pipe operator (|) not allowed"
        if not self.allow_redirects and any(op in command for op in [">", ">>", "<"]):
            return False, "Redirect operators not allowed"

        # Parse command to get the base command
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command"
            base_cmd = os.path.basename(parts[0])
        except ValueError:
            return False, "Invalid command syntax"

        # Check blocklist
        if base_cmd in self.blocked_commands:
            return False, f"Command blocked: {base_cmd}"

        # Check allowlist
        if self.allowed_commands is not None and base_cmd not in self.allowed_commands:
            return False, f"Command not in allowlist: {base_cmd}"

        return True, None

    def _execute(self, **kwargs: Any) -> Any:
        """Execute shell command."""
        import time

        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 30)
        env = kwargs.get("env")
        capture_output = kwargs.get("capture_output", True)

        # Validate command
        allowed, error = self._validate_command(command)
        if not allowed:
            return {
                "stdout": "",
                "stderr": f"Validation error: {error}",
                "return_code": -1,
                "success": False,
                "execution_time": 0,
            }

        # Prepare environment
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)

        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.working_directory,
                env=cmd_env,
                capture_output=capture_output,
                text=True,
                timeout=min(timeout, self.max_execution_time),
            )

            execution_time = time.time() - start_time

            return {
                "stdout": result.stdout if capture_output else "",
                "stderr": result.stderr if capture_output else "",
                "return_code": result.returncode,
                "success": result.returncode == 0,
                "execution_time": execution_time,
            }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "return_code": -1,
                "success": False,
                "execution_time": execution_time,
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_code": -1,
                "success": False,
                "execution_time": execution_time,
            }

    async def _aexecute(self, **kwargs: Any) -> Any:
        """Async version - runs in thread pool."""
        import asyncio
        return await asyncio.to_thread(self._execute, **kwargs)