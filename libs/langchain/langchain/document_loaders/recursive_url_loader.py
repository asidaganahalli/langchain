import asyncio
import logging
import re
from typing import Callable, Iterator, List, Optional, Sequence, Set, Union
from urllib.parse import urljoin, urlparse

import requests

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader

logger = logging.getLogger(__name__)

PREFIXES_TO_IGNORE = ("javascript:", "mailto:", "#")
SUFFIXES_TO_IGNORE = (
    ".css",
    ".js",
    ".ico",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
)
SUFFIXES_TO_IGNORE_REGEX = (
    "(?!" + "|".join([re.escape(s) + "[\#'\"]" for s in SUFFIXES_TO_IGNORE]) + ")"
)
PREFIXES_TO_IGNORE_REGEX = (
    "(?!" + "|".join([re.escape(s) for s in PREFIXES_TO_IGNORE]) + ")"
)
DEFAULT_LINK_REGEX = (
    f"href=[\"']{PREFIXES_TO_IGNORE_REGEX}((?:{SUFFIXES_TO_IGNORE_REGEX}.)*?)[\#\"']"
)


def _metadata_extractor(raw_html: str, url: str) -> dict:
    """Build metadata from BeautifulSoup output."""
    metadata = {"source": url}

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning(
            "The bs4 package is required for default metadata extraction. "
            "Please install it with `pip install bs4`."
        )
        return metadata
    soup = BeautifulSoup(raw_html, "html.parser")
    if title := soup.find("title"):
        metadata["title"] = title.get_text()
    if description := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description.get("content", None)
    if html := soup.find("html"):
        metadata["language"] = html.get("lang", None)
    return metadata


def _get_sub_links(
    raw_html: str,
    base_url: str,
    *,
    pattern: Union[str, re.Pattern] = DEFAULT_LINK_REGEX,
    prevent_outside: bool = True,
) -> List[str]:
    """Extract all links from a raw html string and convert into absolute paths.

    Args:
        raw_html: original html
        base_url: the base url of the html
        pattern: Regex to use for extracting links from raw html.
        prevent_outside: If True, ignore external links which are not children
            of the base url.

    Returns:
        List[str]: sub links
    """
    all_links = set(re.findall(pattern, raw_html))
    absolute_paths = set()
    for link in all_links:
        # Some may be absolute links like https://to/path
        if link.startswith("http"):
            if not prevent_outside or link.startswith(base_url):
                absolute_paths.add(link)
        # Some may have omitted the protocol like //to/path
        elif link.startswith("//"):
            absolute_paths.add(f"{urlparse(base_url).scheme}:{link}")
        else:
            absolute_paths.add(urljoin(base_url, link))
    return list(absolute_paths)


class RecursiveUrlLoader(BaseLoader):
    """Load all child links from a URL page."""

    def __init__(
        self,
        url: str,
        max_depth: Optional[int] = 2,
        use_async: Optional[bool] = None,
        extractor: Optional[Callable[[str], str]] = None,
        metadata_extractor: Optional[Callable[[str, str], str]] = None,
        exclude_dirs: Optional[Sequence[str]] = (),
        timeout: Optional[int] = 10,
        prevent_outside: Optional[bool] = True,
    ) -> None:
        """Initialize with URL to crawl and any subdirectories to exclude.
        Args:
            url: The URL to crawl.
            max_depth: The max depth of the recursive loading.
            use_async: Whether to use asynchronous loading.
                If True, this function will not be lazy, but it will still work in the
                expected way, just not lazy.
            extractor: A function to extract document contents from raw html.
                When extract function returns an empty string, the document is
                ignored.
            metadata_extractor: A function to extract metadata from raw html and the
                source url (args in that order). Default extractor will attempt
                to use BeautifulSoup4 to extract the title, description and language
                of the page.
            exclude_dirs: A list of subdirectories to exclude.
            timeout: The timeout for the requests, in the unit of seconds.
            prevent_outside: If True, prevent loading from urls which are not children
                of the root url.
        """

        self.url = url
        self.max_depth = max_depth if max_depth is not None else 2
        self.use_async = use_async if use_async is not None else False
        self.extractor = extractor if extractor is not None else lambda x: x
        self.metadata_extractor = (
            metadata_extractor
            if metadata_extractor is not None
            else _metadata_extractor
        )
        self.exclude_dirs = exclude_dirs if exclude_dirs is not None else ()
        self.timeout = timeout if timeout is not None else 10
        self.prevent_outside = prevent_outside if prevent_outside is not None else True

    def _get_child_links_recursive(
        self, url: str, visited: Optional[Set[str]] = None, depth: int = 0
    ) -> Iterator[Document]:
        """Recursively get all child links starting with the path of the input URL.

        Args:
            url: The URL to crawl.
            visited: A set of visited URLs.
            depth: Current depth of recursion. Stop when depth >= max_depth.
        """

        if depth >= self.max_depth:
            return
        # Exclude the links that start with any of the excluded directories
        if any(url.startswith(exclude_dir) for exclude_dir in self.exclude_dirs):
            return

        # Exclude the root and parent from a list
        visited = set() if visited is None else visited

        # Get all links that can be accessed from the current URL
        try:
            response = requests.get(url, timeout=self.timeout)
        except Exception:
            logger.warning(f"Unable to load from {url}")
            return
        content = self.extractor(response.text)
        if content:
            yield Document(
                page_content=content,
                metadata=self.metadata_extractor(response.text, url),
            )
        visited.add(url)

        # Store the visited links and recursively visit the children
        sub_links = _get_sub_links(
            response.text, self.url, prevent_outside=self.prevent_outside
        )
        for link in sub_links:
            # Check all unvisited links
            if link not in visited:
                yield from self._get_child_links_recursive(
                    link, visited=visited, depth=depth + 1
                )

    async def _async_get_child_links_recursive(
        self, url: str, visited: Optional[Set[str]] = None, depth: int = 0
    ) -> List[Document]:
        """Recursively get all child links starting with the path of the input URL.

        Args:
            url: The URL to crawl.
            visited: A set of visited URLs.
            depth: To reach the current url, how many pages have been visited.
        """
        try:
            import aiohttp
        except ImportError:
            raise ImportError(
                "The aiohttp package is required for the RecursiveUrlLoader. "
                "Please install it with `pip install aiohttp`."
            )
        if depth > self.max_depth:
            return []

        # Add a trailing slash if not present
        if not url.endswith("/"):
            url += "/"

        # Exclude the root and parent from a list
        visited = set() if visited is None else visited

        # Exclude the links that start with any of the excluded directories
        if any(url.startswith(exclude_dir) for exclude_dir in self.exclude_dirs):
            return []
        # Disable SSL verification because websites may have invalid SSL certificates,
        # but won't cause any security issues for us.
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=aiohttp.ClientTimeout(self.timeout),
        ) as session:
            # Some url may be invalid, so catch the exception
            response: aiohttp.ClientResponse
            try:
                response = await session.get(url)
                text = await response.text()
            except (aiohttp.client_exceptions.InvalidURL, Exception):
                return []

            sub_links = _get_sub_links(
                text, self.url, prevent_outside=self.prevent_outside
            )

            # Worker will be only called within the current function
            # Worker function will process the link
            # then recursively call get_child_links_recursive to process the children
            async def worker(link: str) -> Union[Document, None]:
                try:
                    async with aiohttp.ClientSession(
                        connector=aiohttp.TCPConnector(ssl=False),
                        timeout=aiohttp.ClientTimeout(self.timeout),
                    ) as session:
                        response = await session.get(link)
                        text = await response.text()
                        content = self.extractor(text)
                        if content:
                            return Document(
                                page_content=content,
                                metadata=self.metadata_extractor(text, link),
                            )
                        else:
                            return None
                # Despite the fact that we have filtered some links,
                # there may still be some invalid links, so catch the exception
                except (aiohttp.client_exceptions.InvalidURL, Exception):
                    return None

            # The coroutines that will be executed
            tasks = []
            # Generate the tasks
            for link in sub_links:
                # Check all unvisited links
                if link not in visited:
                    visited.add(link)
                    tasks.append(worker(link))
            # Get the not None results
            results = list(
                filter(lambda x: x is not None, await asyncio.gather(*tasks))
            )
            # Recursively call the function to get the children of the children
            sub_tasks = []
            for link in sub_links:
                sub_tasks.append(
                    self._async_get_child_links_recursive(link, visited, depth + 1)
                )
            # sub_tasks returns coroutines of list,
            # so we need to flatten the list await asyncio.gather(*sub_tasks)
            flattened = []
            next_results = await asyncio.gather(*sub_tasks)
            for sub_result in next_results:
                if isinstance(sub_result, Exception):
                    # We don't want to stop the whole process, so just ignore it
                    # Not standard html format or invalid url or 404 may cause this
                    # But we can't do anything about it.
                    continue
                if sub_result is not None:
                    flattened += sub_result
            results += flattened
            return list(filter(lambda x: x is not None, results))

    def lazy_load(self) -> Iterator[Document]:
        """Lazy load web pages.
        When use_async is True, this function will not be lazy,
        but it will still work in the expected way, just not lazy."""
        if self.use_async:
            results = asyncio.run(self._async_get_child_links_recursive(self.url))
            if results is None:
                return iter([])
            else:
                return iter(results)
        else:
            return self._get_child_links_recursive(self.url)

    def load(self) -> List[Document]:
        """Load web pages."""
        return list(self.lazy_load())
