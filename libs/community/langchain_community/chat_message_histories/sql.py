import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Union

from langchain_core._api import deprecated, warn_deprecated
from sqlalchemy import Column, Integer, Text, delete, select

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    BaseMessage,
    message_to_dict,
    messages_from_dict,
)
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    declarative_base,
    scoped_session,
    sessionmaker,
)

logger = logging.getLogger(__name__)


class BaseMessageConverter(ABC):
    """Convert BaseMessage to the SQLAlchemy model."""

    @abstractmethod
    def from_sql_model(self, sql_message: Any) -> BaseMessage:
        """Convert a SQLAlchemy model to a BaseMessage instance."""
        raise NotImplementedError

    @abstractmethod
    def to_sql_model(self, message: BaseMessage, session_id: str) -> Any:
        """Convert a BaseMessage instance to a SQLAlchemy model."""
        raise NotImplementedError

    @abstractmethod
    def get_sql_model_class(self) -> Any:
        """Get the SQLAlchemy model class."""
        raise NotImplementedError


def create_message_model(table_name: str, DynamicBase: Any) -> Any:
    """
    Create a message model for a given table name.

    Args:
        table_name: The name of the table to use.
        DynamicBase: The base class to use for the model.

    Returns:
        The model class.

    """

    # Model declared inside a function to have a dynamic table name.
    class Message(DynamicBase):  # type: ignore[valid-type, misc]
        __tablename__ = table_name
        id = Column(Integer, primary_key=True)
        session_id = Column(Text)
        message = Column(Text)

    return Message


class DefaultMessageConverter(BaseMessageConverter):
    """The default message converter for SQLChatMessageHistory."""

    def __init__(self, table_name: str):
        self.model_class = create_message_model(table_name, declarative_base())

    def from_sql_model(self, sql_message: Any) -> BaseMessage:
        return messages_from_dict([json.loads(sql_message.message)])[0]

    def to_sql_model(self, message: BaseMessage, session_id: str) -> Any:
        return self.model_class(
            session_id=session_id, message=json.dumps(message_to_dict(message))
        )

    def get_sql_model_class(self) -> Any:
        return self.model_class


DBConnection = Union[AsyncEngine, Engine, str]


class SQLChatMessageHistory(BaseChatMessageHistory):
    """Chat message history stored in an SQL database."""

    @property
    @deprecated("0.2.2", removal="0.3.0", alternative="session_maker")
    def Session(self) -> Union[scoped_session, async_sessionmaker]:
        return self.session_maker

    def __init__(
            self,
            session_id: str,
            connection_string: Optional[str] = None,
            table_name: str = "message_store",
            session_id_field_name: str = "session_id",
            custom_message_converter: Optional[BaseMessageConverter] = None,
            connection: Union[None, DBConnection] = None,
            engine_args: Optional[Dict[str, Any]] = None,
            async_mode: Optional[bool] = None,  # Use only if connection is a string
    ):
        assert not (connection_string and connection), \
            "connection_string and connection are mutually exclusive"
        if connection_string:
            warn_deprecated(
                since="0.2.2",
                removal="0.3.0",
                name="connection_string",
                alternative="Use connection instead")
            connection = connection_string
            self.connection_string = connection_string
        if isinstance(connection, str):
            self.async_mode = async_mode
            if async_mode:
                self.async_engine = create_async_engine(
                    connection, **(engine_args or {})
                )
            else:
                self.engine = create_engine(url=connection, **(engine_args or {}))
        elif isinstance(connection, Engine):
            self.async_mode = False
            self.engine = connection
        elif isinstance(connection, AsyncEngine):
            self.async_mode = True
            self.async_engine = connection
        else:
            raise ValueError(
                "connection should be a connection string or an instance of "
                "sqlalchemy.engine.Engine or sqlalchemy.ext.asyncio.engine.AsyncEngine"
            )

        # To be consistent with others SQL implementations, rename to session_maker
        self.session_maker: Union[scoped_session, async_sessionmaker]
        if self.async_mode:
            self.session_maker = async_sessionmaker(bind=self.async_engine)
        else:
            self.session_maker = scoped_session(sessionmaker(bind=self.engine))

        self.session_id_field_name = session_id_field_name
        self.converter = custom_message_converter or DefaultMessageConverter(table_name)
        self.sql_model_class = self.converter.get_sql_model_class()
        if not hasattr(self.sql_model_class, session_id_field_name):
            raise ValueError("SQL model class must have session_id column")
        self._table_created = False
        if not self.async_mode:
            self._create_table_if_not_exists()

        self.session_id = session_id

    def _create_table_if_not_exists(self) -> None:
        self.sql_model_class.metadata.create_all(self.engine)
        self._table_created = True

    async def _acreate_table_if_not_exists(self) -> None:
        if not self._table_created:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(self.sql_model_class.metadata.create_all)
            self._table_created = True

    @property
    def messages(self) -> List[BaseMessage]:  # type: ignore
        """Retrieve all messages from db"""
        assert not self.async_mode, "This method must be called without async_mode"
        with self.session_maker() as session:
            result = (
                session.query(self.sql_model_class)
                .where(
                    getattr(self.sql_model_class, self.session_id_field_name)
                    == self.session_id
                )
                .order_by(self.sql_model_class.id.asc())
            )
            messages = []
            for record in result:
                messages.append(self.converter.from_sql_model(record))
            return messages

    async def aget_messages(self) -> List[BaseMessage]:
        """Retrieve all messages from db"""
        assert self.async_mode, "This method must be called with async_mode"
        await self._acreate_table_if_not_exists()
        async with self.session_maker() as session:
            stmt = (
                select(self.sql_model_class)
                .where(
                    getattr(self.sql_model_class, self.session_id_field_name)
                    == self.session_id
                )
                .order_by(self.sql_model_class.id.asc())
            )
            result = await session.execute(stmt)
            messages = []
            for record in result.scalars():
                messages.append(self.converter.from_sql_model(record))
            return messages

    def add_message(self, message: BaseMessage) -> None:
        """Append the message to the record in db"""
        with self.session_maker() as session:
            session.add(self.converter.to_sql_model(message, self.session_id))
            session.commit()

    async def aadd_message(self, message: BaseMessage) -> None:
        """Add a Message object to the store.

        Args:
            message: A BaseMessage object to store.
        """
        assert self.async_mode, "This method must be called with async_mode"
        await self._acreate_table_if_not_exists()
        async with self.session_maker() as session:
            session.add(self.converter.to_sql_model(message, self.session_id))
            await session.commit()

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        # The method RunnableWithMessageHistory._exit_history() call
        #  add_message method by mistake and not aadd_message.
        # See https://github.com/langchain-ai/langchain/issues/22021
        if self.async_mode:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.aadd_messages(messages))
        else:
            with self.session_maker() as session:
                for message in messages:
                    session.add(self.converter.to_sql_model(message, self.session_id))
                session.commit()

    async def aadd_messages(self, messages: Sequence[BaseMessage]) -> None:
        # Add all messages in one transaction
        assert self.async_mode, "This method must be called with async_mode"
        await self._acreate_table_if_not_exists()
        async with self.session_maker() as session:
            for message in messages:
                session.add(self.converter.to_sql_model(message, self.session_id))
            await session.commit()

    def clear(self) -> None:
        """Clear session memory from db"""

        assert not self.async_mode, "This method must be called without async_mode"
        with self.session_maker() as session:
            session.query(self.sql_model_class).filter(
                getattr(self.sql_model_class, self.session_id_field_name)
                == self.session_id
            ).delete()
            session.commit()

    async def aclear(self) -> None:
        """Clear session memory from db"""

        assert self.async_mode, "This method must be called with async_mode"
        await self._acreate_table_if_not_exists()
        async with self.session_maker() as session:
            stmt = delete(self.sql_model_class).filter(
                getattr(self.sql_model_class, self.session_id_field_name)
                == self.session_id
            )
            await session.execute(stmt)
            await session.commit()
