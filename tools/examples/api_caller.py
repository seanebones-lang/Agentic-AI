"""API caller tool for making HTTP requests."""

from typing import Any, Dict, Optional

import httpx

from tools.tool_manager import BaseTool


class APICallerTool(BaseTool):
    """Tool for calling REST APIs."""

    def __init__(self) -> None:
        """Initialize API caller tool."""
        super().__init__(
            name="api_caller",
            description="Call REST APIs with GET, POST, PUT, DELETE methods. Supports JSON payloads and headers.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The API endpoint URL",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "description": "HTTP method",
                        "default": "GET",
                    },
                    "data": {
                        "type": "object",
                        "description": "JSON payload for POST/PUT/PATCH requests",
                    },
                    "headers": {
                        "type": "object",
                        "description": "HTTP headers",
                    },
                    "params": {
                        "type": "object",
                        "description": "URL query parameters",
                    },
                },
                "required": ["url"],
            },
            returns={
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer"},
                    "data": {"type": "object"},
                    "headers": {"type": "object"},
                },
            },
            category="integration",
            tags=["api", "http", "rest", "web"],
            timeout=30,
        )

    def _execute(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute HTTP request.

        Args:
            url: API endpoint URL
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            data: JSON payload
            headers: HTTP headers
            params: Query parameters

        Returns:
            Dict containing status_code, data, and headers
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(
                method=method.upper(),
                url=url,
                json=data,
                headers=headers,
                params=params,
            )

            # Raise for 4xx/5xx status codes
            response.raise_for_status()

            # Try to parse JSON response
            try:
                response_data = response.json()
            except Exception:
                response_data = {"text": response.text}

            return {
                "status_code": response.status_code,
                "data": response_data,
                "headers": dict(response.headers),
            }

    async def _aexecute(
        self,
        url: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Async version of execute."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                json=data,
                headers=headers,
                params=params,
            )

            response.raise_for_status()

            try:
                response_data = response.json()
            except Exception:
                response_data = {"text": response.text}

            return {
                "status_code": response.status_code,
                "data": response_data,
                "headers": dict(response.headers),
            }

