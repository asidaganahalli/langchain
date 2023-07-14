from __future__ import annotations

from typing import Any, Iterator, List, Optional

from pydantic import BaseModel

from langchain.embeddings.base import Embeddings


def chunk(texts: List[str], size: int) -> Iterator[List[str]]:
    for i in range(0, len(texts), size):
        yield texts[i : i + size]


class MlflowAIGatewayEmbeddings(Embeddings, BaseModel):
    route: str
    gateway_uri: Optional[str] = None

    def __init__(self, **kwargs: Any):
        try:
            import mlflow.gateway
        except ImportError as e:
            raise ImportError(
                "Could not import `mlflow.gateway` module. "
                "Please install it with `pip install mlflow[gateway]`."
            ) from e

        super().__init__(**kwargs)
        if self.gateway_uri:
            mlflow.gateway.set_gateway_uri(self.gateway_uri)

    def _query(self, texts: List[str]) -> List[List[float]]:
        try:
            import mlflow.gateway
        except ImportError as e:
            raise ImportError(
                "Could not import `mlflow.gateway` module. "
                "Please install it with `pip install mlflow[gateway]`."
            ) from e

        embeddings = []
        for txt in chunk(texts, 20):
            resp = mlflow.gateway.query(self.route, data={"text": txt})
            embeddings.append(resp["embeddings"])
        return embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._query(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._query([text])[0]
