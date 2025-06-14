import httpx
import json
from typing import Optional, Dict, Any
from urllib.parse import quote
from .data import DataResult, Data, dataLikeToData
from opentelemetry.propagate import inject
from agentuity import __version__
from opentelemetry import trace
from .types import DataLike


class ObjectStorePutParams:
    """Parameters for object store put operations."""

    def __init__(
        self,
        content_type: Optional[str] = None,
        content_encoding: Optional[str] = None,
        cache_control: Optional[str] = None,
        content_disposition: Optional[str] = None,
        content_language: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ):
        self.content_type = content_type
        self.content_encoding = content_encoding
        self.cache_control = cache_control
        self.content_disposition = content_disposition
        self.content_language = content_language
        self.metadata = metadata or {}


class ObjectStore:
    """
    An object storage client for storing and retrieving objects. This class provides
    methods to interact with object storage, supporting operations like getting,
    putting, deleting objects, and creating public URLs.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        tracer: trace.Tracer,
    ):
        """
        Initialize the ObjectStore client.

        Args:
            base_url: The base URL of the object storage service
            api_key: The API key for authentication
            tracer: OpenTelemetry tracer for distributed tracing
        """
        self.base_url = base_url
        self.api_key = api_key
        self.tracer = tracer

    async def get(self, bucket: str, key: str) -> DataResult:
        """
        Retrieve an object from the object store.

        Args:
            bucket: The bucket to get the object from
            key: The key of the object to get

        Returns:
            DataResult: A container containing the retrieved data if found, or None if not found

        Raises:
            Exception: If the retrieval operation fails
        """
        with self.tracer.start_as_current_span("agentuity.objectstore.get") as span:
            span.set_attribute("bucket", bucket)
            span.set_attribute("key", key)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
            }
            inject(headers)

            response = httpx.get(
                f"{self.base_url}/object/2025-03-17/{quote(bucket, safe='')}/{quote(key, safe='')}",
                headers=headers,
            )

            if response.status_code == 200:
                span.add_event("hit")
                span.set_status(trace.StatusCode.OK)
                import asyncio

                reader = asyncio.StreamReader()
                reader.feed_data(response.content)
                reader.feed_eof()

                content_type = response.headers.get(
                    "Content-Type", "application/octet-stream"
                )
                return DataResult(Data(content_type, reader))
            elif response.status_code == 404:
                span.add_event("miss")
                span.set_status(trace.StatusCode.OK)
                return DataResult(None)
            else:
                error_message = response.text
                span.set_status(trace.StatusCode.ERROR, "Failed to get object")
                span.record_exception(Exception(error_message))
                raise Exception(
                    error_message
                    or f"error getting object: {response.reason_phrase} ({response.status_code})"
                )

    async def put(
        self,
        bucket: str,
        key: str,
        data: DataLike,
        params: Optional[ObjectStorePutParams] = None,
    ) -> None:
        """
        Store an object in the object store.

        Args:
            bucket: The bucket to put the object into
            key: The key of the object to put
            data: The data to put
            params: Optional parameters including content_type, content_encoding,
                   cache_control, content_disposition, content_language, and metadata

        Raises:
            Exception: If the storage operation fails
        """
        with self.tracer.start_as_current_span("agentuity.objectstore.put") as span:
            span.set_attribute("bucket", bucket)
            span.set_attribute("key", key)

            if params:
                if params.content_type:
                    span.set_attribute("contentType", params.content_type)
                if params.content_encoding:
                    span.set_attribute("contentEncoding", params.content_encoding)
                if params.cache_control:
                    span.set_attribute("cacheControl", params.cache_control)
                if params.content_disposition:
                    span.set_attribute("contentDisposition", params.content_disposition)
                if params.content_language:
                    span.set_attribute("contentLanguage", params.content_language)

            try:
                data_obj = dataLikeToData(data, params.content_type if params else None)
                content_type = data_obj.content_type
                payload = await data_obj.binary()
            except Exception as e:
                span.set_status(trace.StatusCode.ERROR, "Failed to encode data")
                raise e

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
                "Content-Type": content_type,
            }

            if params:
                if params.content_encoding:
                    headers["Content-Encoding"] = params.content_encoding
                if params.cache_control:
                    headers["Cache-Control"] = params.cache_control
                if params.content_disposition:
                    headers["Content-Disposition"] = params.content_disposition
                if params.content_language:
                    headers["Content-Language"] = params.content_language

                for key, value in params.metadata.items():
                    headers[f"x-metadata-{key}"] = value

            inject(headers)

            response = httpx.put(
                f"{self.base_url}/object/2025-03-17/{quote(bucket, safe='')}/{quote(key, safe='')}",
                headers=headers,
                content=payload,
            )

            if 200 <= response.status_code < 300:
                span.set_status(trace.StatusCode.OK)
            else:
                error_message = ""
                try:
                    error_message = response.text
                except Exception:
                    error_message = response.reason_phrase

                span.set_status(trace.StatusCode.ERROR, "Failed to put object")
                span.record_exception(Exception(error_message))
                raise Exception(
                    error_message
                    or f"error putting object: {response.reason_phrase} ({response.status_code})"
                )

    async def delete(self, bucket: str, key: str) -> bool:
        """
        Delete an object from the object store.

        Args:
            bucket: The bucket to delete the object from
            key: The key of the object to delete

        Returns:
            bool: True if the object was deleted, False if the object did not exist

        Raises:
            Exception: If the deletion operation fails
        """
        with self.tracer.start_as_current_span("agentuity.objectstore.delete") as span:
            span.set_attribute("bucket", bucket)
            span.set_attribute("key", key)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
            }
            inject(headers)

            response = httpx.delete(
                f"{self.base_url}/object/2025-03-17/{quote(bucket, safe='')}/{quote(key, safe='')}",
                headers=headers,
            )

            if response.status_code == 200:
                span.add_event("deleted", {"deleted": True})
                span.set_status(trace.StatusCode.OK)
                return True
            elif response.status_code == 404:
                span.add_event("not_found", {"deleted": False})
                span.set_status(trace.StatusCode.OK)
                return False
            else:
                error_message = response.text
                span.set_status(trace.StatusCode.ERROR, "Failed to delete object")
                span.record_exception(Exception(error_message))
                raise Exception(
                    error_message
                    or f"error deleting object: {response.reason_phrase} ({response.status_code})"
                )

    async def create_public_url(
        self, bucket: str, key: str, expires_duration: Optional[int] = None
    ) -> str:
        """
        Create a public URL for an object.

        Args:
            bucket: The bucket to create the signed URL for
            key: The key of the object to create the signed URL for
            expires_duration: The duration of the signed URL in milliseconds

        Returns:
            str: The public URL

        Raises:
            Exception: If creating the public URL fails
        """
        with self.tracer.start_as_current_span(
            "agentuity.objectstore.createPublicURL"
        ) as span:
            span.set_attribute("bucket", bucket)
            span.set_attribute("key", key)
            if expires_duration:
                span.set_attribute("expiresDuration", expires_duration)

            path = f"/object/2025-03-17/presigned/{quote(bucket, safe='')}/{quote(key, safe='')}"

            request_body: Dict[str, Any] = {}
            if expires_duration:
                request_body["expires"] = expires_duration

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
                "Content-Type": "application/json",
            }
            inject(headers)

            response = httpx.post(
                f"{self.base_url}{path}",
                headers=headers,
                content=json.dumps(request_body),
            )

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if response_data.get("success"):
                        span.set_status(trace.StatusCode.OK)
                        return response_data["url"]
                    elif response_data.get("message"):
                        raise Exception(response_data["message"])
                except (json.JSONDecodeError, KeyError):
                    pass

            span.set_status(trace.StatusCode.ERROR, "Failed to create public URL")
            raise Exception(
                f"error creating public URL: {response.reason_phrase} ({response.status_code})"
            )
