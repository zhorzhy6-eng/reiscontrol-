"""Verify that the committed object, rather than an upload claim, is hashed."""

import hashlib

from backend.infrastructure.storage import S3ObjectStore


class FakeBody:
    def __init__(self, content: bytes):
        self.content = content
        self.closed = False

    def iter_chunks(self, chunk_size):
        midpoint = len(self.content) // 2
        yield self.content[:midpoint]
        yield self.content[midpoint:]

    def close(self):
        self.closed = True


class FakeS3Client:
    def __init__(self, content: bytes):
        self.content = content
        self.body = FakeBody(content)
        self.calls = []

    def copy_object(self, **kwargs):
        self.calls.append(("copy", kwargs))

    def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        return {"Body": self.body}

    def generate_presigned_url(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        return "https://storage.example/signed"


def test_upload_is_copied_before_hashing_and_read_url_is_short_lived():
    client = FakeS3Client(b"photo-content")
    store = S3ObjectStore.__new__(S3ObjectStore)
    store.bucket = "test"
    store.client = client
    assert store.presign_put("staging/id", "image/jpeg", 900).startswith("https://")
    digest, size = store.commit_copy_and_hash("staging/id", "attachments/id")
    assert digest == hashlib.sha256(b"photo-content").hexdigest()
    assert size == len(b"photo-content")
    assert [name for name, _ in client.calls[1:3]] == ["copy", "get"]
    assert client.body.closed
    store.presign_get("attachments/id", 300)
    assert client.calls[-1][1]["ExpiresIn"] == 300
