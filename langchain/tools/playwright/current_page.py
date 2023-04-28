from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from langchain.tools.base import BaseTool
from langchain.tools.playwright.base import BaseBrowserToolMixin
from langchain.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)


class CurrentWebPageTool(BaseTool, BaseBrowserToolMixin):
    name: str = "current_webpage"
    description: str = "Returns the URL of the current page"
    args_schema: Type[BaseModel] = BaseModel

    def _run(self) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        return str(page.url)

    async def _arun(self) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        return str(page.url)
