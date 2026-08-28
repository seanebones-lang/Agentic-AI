"""Code execution tool for running Python code in a sandbox."""

from typing import Any, Dict, Optional
import tempfile
import os
import subprocess
import json
import sys

from tools.tool_manager import BaseTool


class CodeExecutionTool(BaseTool):
    """Tool for executing Python code in a sandboxed environment."""

    def __init__(
        self,
        allowed_imports: Optional[list] = None,
        blocked_imports: Optional[list] = None,
        max_execution_time: int = 30,
        use_nsjail: bool = True,
        nsjail_path: str = "nsjail",
    ) -> None:
        """
        Initialize code execution tool.

        Args:
            allowed_imports: List of allowed import modules (None = allow all safe)
            blocked_imports: List of blocked import modules
            max_execution_time: Maximum execution time in seconds
            use_nsjail: Use nsjail for true sandboxing (requires nsjail installed)
            nsjail_path: Path to nsjail binary
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
        self.use_nsjail = use_nsjail
        self.nsjail_path = nsjail_path
        
        # Check if nsjail is available
        self._nsjail_available = self._check_nsjail()

    def _check_nsjail(self) -> bool:
        """Check if nsjail binary is available."""
        import shutil
        return shutil.which(self.nsjail_path) is not None

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

        # If nsjail is available and enabled, use it for true sandboxing
        if self.use_nsjail and self._nsjail_available:
            return self._execute_with_nsjail(code, timeout, variables)

        # Fallback: restricted exec environment
        return self._execute_restricted(code, timeout, variables)

    def _execute_with_nsjail(self, code: str, timeout: int, variables: Optional[Dict]) -> Dict[str, Any]:
        """Execute code using nsjail for true sandboxing."""
        import tempfile
        import os

        start_time = time.time()

        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Add variable injection if provided
            if variables:
                for key, value in variables.items():
                    f.write(f"{key} = {json.dumps(value)}\n")
            f.write(code)
            f.write("\n\nimport json\n_result = locals().get('_result')\nif '_result' in locals():\n    print('__RESULT__', json.dumps(_result, default=str))\n")
            temp_file = f.name

        try:
            # nsjail command: isolate filesystem, network, limit CPU/memory
            nsjail_cmd = [
                self.nsjail_path,
                "--mode", "once",
                "--time_limit", str(timeout),
                "--max_cpus", "1",
                "--rlimit_as", "100",  # 100MB memory limit
                "--rlimit_cpu", str(timeout),
                "--rlimit_fsize", "10",  # 10MB file size limit
                "--rlimit_nofile", "16",
                "--disable_clone_newnet",  # Disable network
                "--disable_clone_newuser",
                "--disable_clone_newipc",
                "--disable_clone_newuts",
                "--disable_clone_newcgroup",
                "--disable_clone_newpid",
                "--",  # End of nsjail options
                sys.executable, temp_file,
            ]

            result = subprocess.run(
                nsjail_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5,  # Extra buffer for nsjail overhead
            )

            execution_time = time.time() - start_time

            # Extract return value from stdout if present
            return_value = None
            stdout = result.stdout
            if "__RESULT__" in stdout:
                try:
                    parts = stdout.split("__RESULT__", 1)
                    stdout = parts[0]
                    return_value = json.loads(parts[1].strip())
                except:
                    pass

            return {
                "stdout": stdout,
                "stderr": result.stderr,
                "return_value": return_value,
                "success": result.returncode == 0,
                "execution_time": execution_time,
            }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "return_value": None,
                "success": False,
                "execution_time": execution_time,
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "return_value": None,
                "success": False,
                "execution_time": execution_time,
            }
        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_file)
            except:
                pass

    def _execute_restricted(self, code: str, timeout: int, variables: Optional[Dict]) -> Dict[str, Any]:
        """Fallback restricted execution without nsjail."""
        import time
        import io
        import sys
        from contextlib import redirect_stdout, redirect_stderr

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