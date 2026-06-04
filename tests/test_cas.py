"""Tests for content-addressable storage."""

import hashlib

import pytest

from pipeline.utils.cas import ContentAddressableStore


@pytest.fixture
def cas(tmp_path):
    return ContentAddressableStore(tmp_path / "objects")


class TestComputeHash:
    def test_deterministic(self, cas):
        content = b"hello world"
        assert cas.compute_hash(content) == cas.compute_hash(content)

    def test_matches_hashlib(self, cas):
        content = b"test content"
        expected = hashlib.sha256(content).hexdigest()
        assert cas.compute_hash(content) == expected

    def test_different_content_different_hash(self, cas):
        assert cas.compute_hash(b"aaa") != cas.compute_hash(b"bbb")

    def test_empty_content(self, cas):
        result = cas.compute_hash(b"")
        assert len(result) == 64


class TestStoreAndRetrieve:
    def test_store_returns_hash(self, cas):
        sha = cas.store(b"hello")
        assert len(sha) == 64

    def test_roundtrip(self, cas):
        content = b"the gospel of Jesus Christ"
        sha = cas.store(content)
        assert cas.retrieve(sha) == content

    def test_idempotent_store(self, cas):
        content = b"same content"
        sha1 = cas.store(content)
        sha2 = cas.store(content)
        assert sha1 == sha2

    def test_retrieve_nonexistent_raises(self, cas):
        with pytest.raises(FileNotFoundError):
            cas.retrieve("0" * 64)

    def test_exists_after_store(self, cas):
        sha = cas.store(b"check existence")
        assert cas.exists(sha) is True

    def test_not_exists_before_store(self, cas):
        assert cas.exists("0" * 64) is False

    def test_corruption_detection(self, cas):
        content = b"original content"
        sha = cas.store(content)
        object_path = cas.objects_dir / sha
        object_path.write_bytes(b"corrupted content")
        with pytest.raises(ValueError, match="Corruption detected"):
            cas.retrieve(sha)


class TestStoreCreatesDirectory:
    def test_creates_objects_dir(self, tmp_path):
        cas = ContentAddressableStore(tmp_path / "nested" / "objects")
        cas.store(b"test")
        assert (tmp_path / "nested" / "objects").is_dir()
