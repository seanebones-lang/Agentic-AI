"""Code execution tool for running Python code in a sandbox."""

from typing import Any, Dict, Optional
import tempfile
import os
import subprocess
import json

from tools.tool_manager import BaseTool


class CodeExecutionTool(BaseTool):
    """Tool for executing Python code in a sandboxed environment."""

    def __init__(
        self,
        allowed_imports: Optional[list] = None,
        blocked_imports: Optional[list] = None,
        max_execution_time: int = 30,
    ) -> None:
        """
        Initialize code execution tool.

        Args:
            allowed_imports: List of allowed import modules (None = allow all safe)
            blocked_imports: List of blocked import modules
            max_execution_time: Maximum execution time in seconds
        """
        super().__init__(
            name="code_execution",
            description="Execute Python code in a sandboxed environment. Supports data analysis, calculations, and script execution.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Execution timeout in seconds",
                        "default": 30,
                    },
                    "variables": {
                        "type": "object",
                        "description": "Pre-defined variables to inject into execution context",
                    },
                },
                "required": ["code"],
            },
            returns={
                "type": "object",
                "properties": {
                    "stdout": {"type": "string"},
                    "stderr": {"type": "string"},
                    "return_value": {"type": ["string", "object", "array", "number", "boolean"]},
                    "success": {"type": "boolean"},
                    "execution_time": {"type": "number"},
                },
            },
            category="compute",
            tags=["code", "python", "execution", "sandbox", "compute"],
            timeout=max_execution_time,
        )
        self.allowed_imports = allowed_imports
        self.blocked_imports = blocked_imports or [
            "os", "sys", "subprocess", "shutil", "pathlib",
            "socket", "requests", "urllib", "http",
            "importlib", "pkgutil", "runpy",
            "multiprocessing", "threading", "asyncio",
            "ctypes", "cffi", "sysconfig",
        ]
        self.max_execution_time = max_execution_time

    def _check_imports(self, code: str) -> tuple[bool, Optional[str]]:
        """Check if code contains blocked imports."""
        import ast

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.blocked_imports:
                            return False, f"Blocked import: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module in self.blocked_imports:
                        return False, f"Blocked import: {node.module}"
        except SyntaxError:
            return False, "Syntax error in code"
        return True, None

    def _execute(self, **kwargs: Any) -> Any:
        """
        Execute Python code in sandbox.

        Args:
            code: Python code to execute
            timeout: Execution timeout
            variables: Pre-defined variables

        Returns:
            Dict with stdout, stderr, return_value, success, execution_time
        """
        code = kwargs.get("code", "")
        timeout = kwargs.get("timeout", self.max_execution_time)
        variables = kwargs.get("variables")

        import time

        # Security check
        allowed, error = self._check_imports(code)
        if not allowed:
            return {
                "stdout": "",
                "stderr": f"Security error: {error}",
                "return_value": None,
                "success": False,
                "execution_time": 0,
            }

        # Prepare execution environment
        exec_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "reversed": reversed,
                "isinstance": isinstance,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                "type": type,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "Exception": Exception,
            },
            "json": json,
        }

        # Add allowed imports
        safe_modules = {
            "math", "random", "datetime", "decimal", "fractions",
            "statistics", "itertools", "collections", "functools",
            "string", "re", "hashlib", "base64", "uuid",
        }
        if self.allowed_imports:
            safe_modules.update(self.allowed_imports)

        for mod_name in safe_modules:
            try:
                exec_globals[mod_name] = __import__(mod_name)
            except ImportError:
                pass

        # Inject user variables
        if variables:
            exec_globals.update(variables)

        # Capture stdout/stderr
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        start_time = time.time()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Execute code
                exec(code, exec_globals)

            execution_time = time.time() - start_time

            # Get return value if last expression has one
            return_value = exec_globals.get("_result", None)

            return {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
                "return_value": return_value,
                "success": True,
                "execution_time": execution_time,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue() + f"\n{e.__class__.__name__}: {str(e)}",
                "return_value": None,
                "success": False,
                "execution_time": execution_time,
            }

    async def _aexecute(self, **kwargs: Any) -> Any:
        """Async version - runs in thread pool."""
        import asyncio
        return await asyncio.to_thread(self._execute, **kwargs)