from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.base import BaseTool
from langchain.tools.playwright.base import BaseBrowserToolMixin
from langchain.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)


class NavigateToolInput(BaseModel):
    """Input for NavigateToolInput."""

    url: str = Field(..., description="url to navigate to")


class NavigateTool(BaseTool, BaseBrowserToolMixin):
    name: str = "navigate_browser"
    description: str = "Navigate a browser to the specified URL"
    args_schema: Type[BaseModel] = NavigateToolInput

    def _run(self, url: str) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        response = page.goto(url)
        status = response.status if response else "unknown"
        return f"Navigating to {url} returned status code {status}"

    async def _arun(self, url: str) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        response = await page.goto(url)
        status = response.status if response else "unknown"
        return f"Navigating to {url} returned status code {status}"
