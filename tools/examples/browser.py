"""Browser automation tool for web scraping and interaction."""

from typing import Any, Dict, List, Optional
import asyncio

from tools.tool_manager import BaseTool


class BrowserTool(BaseTool):
    """Tool for browser automation using Playwright."""

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        viewport: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Initialize browser tool.

        Args:
            headless: Run browser in headless mode
            browser_type: Browser type ('chromium', 'firefox', 'webkit')
            viewport: Viewport size {'width': 1280, 'height': 720}
        """
        super().__init__(
            name="browser",
            description="Automate web browser for scraping, interaction, and screenshots. Supports navigation, clicking, form filling, and data extraction.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "navigate",
                            "click",
                            "type",
                            "extract_text",
                            "extract_html",
                            "screenshot",
                            "wait",
                            "evaluate",
                        ],
                        "description": "Browser action to perform",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to (for navigate action)",
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for element (click, type, extract)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type (for type action)",
                    },
                    "wait_time": {
                        "type": "integer",
                        "description": "Time to wait in milliseconds",
                        "default": 1000,
                    },
                    "script": {
                        "type": "string",
                        "description": "JavaScript to evaluate (for evaluate action)",
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture full page screenshot",
                        "default": False,
                    },
                },
                "required": ["action"],
            },
            returns={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "data": {"type": ["string", "object", "array"]},
                    "error": {"type": "string"},
                },
            },
            category="web",
            tags=["browser", "playwright", "scraping", "automation", "web"],
            timeout=60,
        )
        self.headless = headless
        self.browser_type = browser_type
        self.viewport = viewport or {"width": 1280, "height": 720}
        self._browser = None
        self._page = None
        self._playwright = None

    async def _get_page(self):
        """Get or create browser page."""
        if self._page and not self._page.is_closed():
            return self._page

        if not self._playwright:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

        if not self._browser or not self._browser.is_connected():
            browser_class = getattr(self._playwright, self.browser_type)
            self._browser = await browser_class.launch(headless=self.headless)

        context = await self._browser.new_context(viewport=self.viewport)
        self._page = await context.new_page()
        return self._page

    def _execute(self, **kwargs: Any) -> Any:
        """Execute browser action."""
        import asyncio

        action = kwargs.get("action", "")

        try:
            return asyncio.run(self._execute_async(action, kwargs))
        except Exception as e:
            self.logger.error("Browser action failed", action=action, error=str(e))
            return {
                "success": False,
                "data": None,
                "error": str(e),
            }

    async def _execute_async(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Async browser action execution."""
        page = await self._get_page()

        if action == "navigate":
            url = params.get("url")
            if not url:
                return {"success": False, "error": "URL required for navigate action"}
            await page.goto(url, wait_until="networkidle")
            return {"success": True, "data": {"url": page.url, "title": await page.title()}}

        elif action == "click":
            selector = params.get("selector")
            if not selector:
                return {"success": False, "error": "Selector required for click action"}
            await page.click(selector)
            return {"success": True, "data": {"clicked": selector}}

        elif action == "type":
            selector = params.get("selector")
            text = params.get("text", "")
            if not selector:
                return {"success": False, "error": "Selector required for type action"}
            await page.fill(selector, text)
            return {"success": True, "data": {"typed": text, "selector": selector}}

        elif action == "extract_text":
            selector = params.get("selector")
            if not selector:
                return {"success": False, "error": "Selector required for extract_text action"}
            text = await page.inner_text(selector)
            return {"success": True, "data": {"text": text}}

        elif action == "extract_html":
            selector = params.get("selector")
            if not selector:
                return {"success": False, "error": "Selector required for extract_html action"}
            html = await page.inner_html(selector)
            return {"success": True, "data": {"html": html}}

        elif action == "screenshot":
            full_page = params.get("full_page", False)
            screenshot = await page.screenshot(full_page=full_page)
            import base64
            return {"success": True, "data": {"screenshot_base64": base64.b64encode(screenshot).decode()}}

        elif action == "wait":
            wait_time = params.get("wait_time", 1000)
            await page.wait_for_timeout(wait_time)
            return {"success": True, "data": {"waited_ms": wait_time}}

        elif action == "evaluate":
            script = params.get("script")
            if not script:
                return {"success": False, "error": "Script required for evaluate action"}
            result = await page.evaluate(script)
            return {"success": True, "data": {"result": result}}

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    async def _aexecute(self, **kwargs: Any) -> Any:
        """Async version."""
        return await self._execute_async(kwargs.get("action", ""), kwargs)

    async def close(self):
        """Close browser and playwright."""
        if self._page and not self._page.is_closed():
            await self._page.close()
        if self._browser and self._browser.is_connected():
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()