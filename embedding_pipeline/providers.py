from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import sqrt
from typing import Any

import requests

from .config import Settings
from .retry import with_retry


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dimensions: int


class EmbeddingProvider(ABC):
    model_name: str

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        retry_attempts: int = 5,
        retry_base_seconds: float = 1.0,
    ) -> None:
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model_name = model
        self.retry_attempts = retry_attempts
        self.retry_base_seconds = retry_base_seconds

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        def call():
            return self.client.embeddings.create(model=self.model_name, input=texts)

        response = with_retry(call, attempts=self.retry_attempts, base_seconds=self.retry_base_seconds)
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered]
        return EmbeddingResult(vectors=vectors, model=response.model or self.model_name, dimensions=len(vectors[0]))


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        retry_attempts: int = 5,
        retry_base_seconds: float = 1.0,
    ) -> None:
        from google import genai
        from google.genai import types

        self.client = genai.Client(api_key=api_key)
        self.types = types
        self.model_name = model
        self.dimensions = dimensions
        self.retry_attempts = retry_attempts
        self.retry_base_seconds = retry_base_seconds

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        vectors: list[list[float]] = []

        def embed_one(text: str):
            return self.client.models.embed_content(
                model=self.model_name,
                contents=text,
                config=self.types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )

        for text in texts:
            response = with_retry(lambda text=text: embed_one(text), attempts=self.retry_attempts, base_seconds=self.retry_base_seconds)
            embedding = response.embeddings[0].values
            vectors.append(normalize_vector([float(value) for value in embedding]))
        return EmbeddingResult(vectors=vectors, model=self.model_name, dimensions=len(vectors[0]))


class CompatibleHttpEmbeddingProvider(EmbeddingProvider):
    """OpenAI-style /embeddings provider for vendor gateways and proxy APIs."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        retry_attempts: int = 5,
        retry_base_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.retry_attempts = retry_attempts
        self.retry_base_seconds = retry_base_seconds

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        url = f"{self.base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model_name, "input": texts}

        def call():
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"{response.status_code} from embedding endpoint: {response.text[:300]}")
            response.raise_for_status()
            return response.json()

        data = with_retry(call, attempts=self.retry_attempts, base_seconds=self.retry_base_seconds)
        vectors = parse_compatible_response(data)
        return EmbeddingResult(vectors=vectors, model=data.get("model", self.model_name), dimensions=len(vectors[0]))


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Native Ollama /api/embed provider."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        retry_attempts: int = 5,
        retry_base_seconds: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.retry_attempts = retry_attempts
        self.retry_base_seconds = retry_base_seconds

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        url = f"{self.base_url}/api/embed"
        payload = {"model": self.model_name, "input": texts}

        def call():
            response = requests.post(url, json=payload, timeout=180)
            if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"{response.status_code} from Ollama embed endpoint: {response.text[:300]}")
            response.raise_for_status()
            return response.json()

        data = with_retry(call, attempts=self.retry_attempts, base_seconds=self.retry_base_seconds)
        vectors = parse_ollama_embed_response(data)
        return EmbeddingResult(vectors=vectors, model=data.get("model", self.model_name), dimensions=len(vectors[0]))


class LocalSentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, *, model: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "Local provider requires sentence-transformers. Install it with: "
                "pip install sentence-transformers"
            ) from exc
        self.model_name = model
        self.model = SentenceTransformer(model)

    def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        vectors = self.model.encode(texts, normalize_embeddings=True).tolist()
        return EmbeddingResult(vectors=vectors, model=self.model_name, dimensions=len(vectors[0]))


def parse_compatible_response(data: dict[str, Any]) -> list[list[float]]:
    if "data" in data:
        rows = data["data"]
        try:
            ordered = sorted(rows, key=lambda item: item.get("index", 0))
            return [row["embedding"] for row in ordered]
        except (TypeError, KeyError) as exc:
            raise ValueError("Compatible embedding response data[] must include embedding vectors") from exc
    if "embeddings" in data:
        return data["embeddings"]
    raise ValueError("Embedding response must contain either data[].embedding or embeddings")


def parse_ollama_embed_response(data: dict[str, Any]) -> list[list[float]]:
    if "embeddings" in data:
        return data["embeddings"]
    if "embedding" in data:
        return [data["embedding"]]
    raise ValueError("Ollama embed response must contain embeddings or embedding")


def normalize_vector(vector: list[float]) -> list[float]:
    magnitude = sqrt(sum(value * value for value in vector))
    if magnitude <= 0:
        return vector
    return [value / magnitude for value in vector]


def build_provider(settings: Settings) -> EmbeddingProvider:
    if settings.provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for EMBEDDING_PROVIDER=gemini")
        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_embedding_model,
            dimensions=settings.embedding_dimensions,
            retry_attempts=settings.retry_attempts,
            retry_base_seconds=settings.retry_base_seconds,
        )
    if settings.provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            retry_attempts=settings.retry_attempts,
            retry_base_seconds=settings.retry_base_seconds,
        )
    if settings.provider == "compatible":
        if not settings.compatible_base_url:
            raise ValueError("COMPATIBLE_BASE_URL is required for EMBEDDING_PROVIDER=compatible")
        return CompatibleHttpEmbeddingProvider(
            api_key=settings.compatible_api_key,
            base_url=settings.compatible_base_url,
            model=settings.compatible_embedding_model,
            retry_attempts=settings.retry_attempts,
            retry_base_seconds=settings.retry_base_seconds,
        )
    if settings.provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
            retry_attempts=settings.retry_attempts,
            retry_base_seconds=settings.retry_base_seconds,
        )
    return LocalSentenceTransformerProvider(model=settings.local_embedding_model)
