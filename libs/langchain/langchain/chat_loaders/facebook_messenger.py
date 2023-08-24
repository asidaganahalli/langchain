import json
import logging
from pathlib import Path
from typing import Iterator, Union

from langchain.chat_loaders.base import BaseChatLoader, ChatSession
from langchain.schema.messages import HumanMessage

logger = logging.getLogger(__file__)


class SingleFileFacebookMessengerChatLoader(BaseChatLoader):
    """A chat loader for loading Facebook Messenger chat data from a single file.

    Args:
        file_path (Union[Path, str]): The path to the chat file.

    Attributes:
        file_path (Path): The path to the chat file.

    """

    def __init__(self, file_path: Union[Path, str]) -> None:
        super().__init__()
        self.file_path = file_path if isinstance(file_path, Path) else Path(file_path)

    def lazy_load(self) -> Iterator[ChatSession]:
        """Lazy loads the chat data from the file.

        Yields:
            ChatSession: A chat session containing the loaded messages.

        """
        with open(self.file_path) as f:
            data = json.load(f)
        sorted_data = sorted(data["messages"], key=lambda x: x["timestamp_ms"])
        messages = []
        for m in sorted_data:
            messages.append(
                HumanMessage(
                    content=m["content"], additional_kwargs={"sender": m["sender_name"]}
                )
            )
        yield ChatSession(messages=messages)


class FolderFacebookMessengerChatLoader(BaseChatLoader):
    """A chat loader for loading Facebook Messenger chat data from a folder.

    Args:
        directory_path (Union[str, Path]): The path to the directory
            containing the chat files.

    Attributes:
        directory_path (Path): The path to the directory containing the chat files.

    """

    def __init__(self, directory_path: Union[str, Path]) -> None:
        super().__init__()
        self.directory_path = (
            Path(directory_path) if isinstance(directory_path, str) else directory_path
        )

    def lazy_load(self) -> Iterator[ChatSession]:
        """Lazy loads the chat data from the folder.

        Yields:
            ChatSession: A chat session containing the loaded messages.

        """
        inbox_path = self.directory_path / "inbox"
        for _dir in inbox_path.iterdir():
            if _dir.is_dir():
                for _file in _dir.iterdir():
                    if _file.suffix.lower() == ".json":
                        file_loader = SingleFileFacebookMessengerChatLoader(
                            file_path=_file
                        )
                        for result in file_loader.lazy_load():
                            yield result
