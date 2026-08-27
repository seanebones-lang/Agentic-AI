"""Web search tool using multiple search providers."""

from typing import Any, Dict, List, Optional
import httpx
import os

from tools.tool_manager import BaseTool


class WebSearchTool(BaseTool):
    """Tool for web search using multiple providers (Brave, SerpAPI, DuckDuckGo)."""

    def __init__(
        self,
        provider: str = "brave",
        api_key: Optional[str] = None,
        max_results: int = 10,
    ) -> None:
        """
        Initialize web search tool.

        Args:
            provider: Search provider ('brave', 'serpapi', 'duckduckgo')
            api_key: API key for the provider
            max_results: Maximum number of results to return
        """
        super().__init__(
            name="web_search",
            description="Search the web for information. Returns titles, URLs, and snippets.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                    "recency_days": {
                        "type": "integer",
                        "description": "Filter results to last N days",
                    },
                },
                "required": ["query"],
            },
            returns={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "snippet": {"type": "string"},
                            },
                        },
                    },
                    "query": {"type": "string"},
                    "provider": {"type": "string"},
                },
            },
            category="research",
            tags=["search", "web", "research", "information"],
            timeout=30,
        )
        self.provider = provider.lower()
        self.api_key = api_key or os.getenv(f"{self.provider.upper()}_API_KEY")
        self.max_results = max_results

        # Provider configurations
        self._providers = {
            "brave": {
                "url": "https://api.search.brave.com/res/v1/web/search",
                "headers": {"Accept": "application/json", "X-Subscription-Token": ""},
                "params_map": {"q": "query", "count": "max_results", "freshness": "recency_days"},
            },
            "serpapi": {
                "url": "https://serpapi.com/search",
                "params_map": {"q": "query", "num": "max_results", "tbs": "recency_days"},
            },
            "duckduckgo": {
                "url": "https://html.duckduckgo.com/html/",
                "method": "POST",
            },
        }

    def _execute(self, **kwargs: Any) -> Any:
        """Execute web search."""
        import asyncio

        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", self.max_results)
        recency_days = kwargs.get("recency_days")

        try:
            return asyncio.run(self._search_async(query, max_results, recency_days))
        except Exception as e:
            self.logger.error("Web search failed", error=str(e))
            return {
                "results": [],
                "query": query,
                "provider": self.provider,
                "error": str(e),
            }

    async def _search_async(
        self,
        query: str,
        max_results: int,
        recency_days: Optional[int],
    ) -> Dict[str, Any]:
        """Async search implementation."""
        if self.provider == "brave":
            return await self._search_brave(query, max_results, recency_days)
        elif self.provider == "serpapi":
            return await self._search_serpapi(query, max_results, recency_days)
        elif self.provider == "duckduckgo":
            return await self._search_duckduckgo(query, max_results)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _search_brave(
        self,
        query: str,
        max_results: int,
        recency_days: Optional[int],
    ) -> Dict[str, Any]:
        """Search using Brave Search API."""
        if not self.api_key:
            return {"results": [], "query": query, "provider": "brave", "error": "Brave API key not configured"}

        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        params = {"q": query, "count": min(max_results, 20)}

        if recency_days:
            params["freshness"] = f"pd{recency_days}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("web", {}).get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })

        return {"results": results, "query": query, "provider": "brave"}

    async def _search_serpapi(
        self,
        query: str,
        max_results: int,
        recency_days: Optional[int],
    ) -> Dict[str, Any]:
        """Search using SerpAPI."""
        if not self.api_key:
            return {"results": [], "query": query, "provider": "serpapi", "error": "SerpAPI key not configured"}

        params = {
            "q": query,
            "num": min(max_results, 100),
            "api_key": self.api_key,
            "engine": "google",
        }

        if recency_days:
            params["tbs"] = f"qdr:d{recency_days}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get("https://serpapi.com/search", params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("organic_results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })

        return {"results": results, "query": query, "provider": "serpapi"}

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
    ) -> Dict[str, Any]:
        """Search using DuckDuckGo HTML scraping (no API key needed)."""
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; AgenticAI/1.0)"},
            )
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for result in soup.select(".result__snippet"):
            link = result.find_previous("a", class_="result__url")
            title_elem = result.find_previous("a", class_="result__title")

            if title_elem and link:
                results.append({
                    "title": title_elem.get_text(strip=True),
                    "url": link.get("href", ""),
                    "snippet": result.get_text(strip=True),
                })

            if len(results) >= max_results:
                break

        return {"results": results, "query": query, "provider": "duckduckgo"}

    async def _aexecute(self, **kwargs: Any) -> Any:
        """Async version."""
        return await self._search_async(
            kwargs.get("query", ""),
            kwargs.get("max_results", self.max_results),
            kwargs.get("recency_days"),
        )