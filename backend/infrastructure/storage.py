"""S3 compatible object storage with presigned upload and immutable committed keys."""

import hashlib
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class StorageError(RuntimeError):
    """Object Storage failed; callers should retry without exposing provider details."""


class ObjectStore(Protocol):
    """Storage operations needed by the attachment application boundary."""

    def presign_put(self, key: str, mime: str, expires_seconds: int) -> str:
        """Return a short-lived PUT URL bound to the declared MIME type."""

    def commit_copy_and_hash(self, source_key: str, final_key: str) -> tuple[str, int]:
        """Copy an upload to an unshared key and hash the copied bytes."""

    def presign_get(self, key: str, expires_seconds: int) -> str:
        """Return a short-lived read URL."""


class S3ObjectStore:
    """Boto3 adapter for Yandex Object Storage's S3 compatible endpoint."""

    def __init__(self, *, endpoint_url: str, bucket: str, region: str) -> None:
        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region)

    def presign_put(self, key: str, mime: str, expires_seconds: int) -> str:
        try:
            return self.client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": mime},
                ExpiresIn=expires_seconds,
                HttpMethod="PUT",
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageError("Object Storage unavailable") from error

    def commit_copy_and_hash(self, source_key: str, final_key: str) -> tuple[str, int]:
        try:
            self.client.copy_object(
                Bucket=self.bucket,
                Key=final_key,
                CopySource={"Bucket": self.bucket, "Key": source_key},
            )
            response = self.client.get_object(Bucket=self.bucket, Key=final_key)
        except (BotoCoreError, ClientError) as error:
            raise StorageError("Object Storage unavailable") from error
        digest = hashlib.sha256()
        size = 0
        body = response["Body"]
        try:
            try:
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        size += len(chunk)
            except (BotoCoreError, ClientError) as error:
                raise StorageError("Object Storage unavailable") from error
        finally:
            body.close()
        return digest.hexdigest(), size

    def presign_get(self, key: str, expires_seconds: int) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_seconds,
                HttpMethod="GET",
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageError("Object Storage unavailable") from error
