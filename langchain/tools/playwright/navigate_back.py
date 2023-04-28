from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from langchain.tools.base import BaseTool
from langchain.tools.playwright.base import BaseBrowserToolMixin
from langchain.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)


class NavigateBackTool(BaseTool, BaseBrowserToolMixin):
    """Navigate back to the previous page in the browser history."""

    name: str = "previous_webpage"
    description: str = "Navigate back to the previous page in the browser history"
    args_schema: Type[BaseModel] = BaseModel

    def _run(self) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        response = page.go_back()

        if response:
            return (
                f"Navigated back to the previous page with URL '{response.url}'."
                f" Status code {response.status}"
            )
        else:
            return "Unable to navigate back; no previous page in the history"

    async def _arun(self) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        response = await page.go_back()

        if response:
            return (
                f"Navigated back to the previous page with URL '{response.url}'."
                f" Status code {response.status}"
            )
        else:
            return "Unable to navigate back; no previous page in the history"
