"""File operations tool for reading, writing, and processing files."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from tools.tool_manager import BaseTool


class FileOperationsTool(BaseTool):
    """Tool for file system operations."""

    def __init__(self, base_directory: Optional[str] = None) -> None:
        """
        Initialize file operations tool.

        Args:
            base_directory: Base directory for file operations (for security)
        """
        super().__init__(
            name="file_operations",
            description="Perform file operations: read, write, list, delete files. Supports text and JSON files.",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list", "delete", "exists"],
                        "description": "File operation to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write operation)",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding",
                        "default": "utf-8",
                    },
                },
                "required": ["operation", "path"],
            },
            returns={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": ["string", "array", "boolean"]},
                },
            },
            category="filesystem",
            tags=["file", "filesystem", "io", "storage"],
            timeout=30,
        )
        self.base_directory = Path(base_directory) if base_directory else Path.cwd()

    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve file path.

        Args:
            path: File path to validate

        Returns:
            Resolved Path object

        Raises:
            ValueError: If path is outside base directory
        """
        file_path = (self.base_directory / path).resolve()

        # Security check: ensure path is within base directory
        if not str(file_path).startswith(str(self.base_directory.resolve())):
            raise ValueError(f"Path {path} is outside base directory")

        return file_path

    def _execute(
        self,
        operation: str,
        path: str,
        content: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """
        Execute file operation.

        Args:
            operation: Operation to perform (read, write, list, delete, exists)
            path: File or directory path
            content: Content to write (for write operation)
            encoding: File encoding

        Returns:
            Dict containing success status and operation result
        """
        file_path = self._validate_path(path)

        if operation == "read":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            content_data = file_path.read_text(encoding=encoding)
            return {"success": True, "data": content_data}

        elif operation == "write":
            if content is None:
                raise ValueError("Content is required for write operation")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding=encoding)
            return {"success": True, "data": f"Written {len(content)} characters"}

        elif operation == "list":
            if not file_path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")
            if not file_path.is_dir():
                raise ValueError(f"Path is not a directory: {path}")
            files = [str(f.relative_to(file_path)) for f in file_path.iterdir()]
            return {"success": True, "data": files}

        elif operation == "delete":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            if file_path.is_file():
                file_path.unlink()
            else:
                import shutil

                shutil.rmtree(file_path)
            return {"success": True, "data": f"Deleted {path}"}

        elif operation == "exists":
            exists = file_path.exists()
            return {"success": True, "data": exists}

        else:
            raise ValueError(f"Unknown operation: {operation}")

    async def _aexecute(
        self,
        operation: str,
        path: str,
        content: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Async version of execute."""
        file_path = self._validate_path(path)

        if operation == "read":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            async with aiofiles.open(file_path, "r", encoding=encoding) as f:
                content_data = await f.read()
            return {"success": True, "data": content_data}

        elif operation == "write":
            if content is None:
                raise ValueError("Content is required for write operation")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(file_path, "w", encoding=encoding) as f:
                await f.write(content)
            return {"success": True, "data": f"Written {len(content)} characters"}

        else:
            # Fall back to sync for other operations
            return self._execute(operation, path, content, encoding)

