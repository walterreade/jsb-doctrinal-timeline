"""Content-addressable storage for immutable documents."""

import hashlib
from pathlib import Path


class ContentAddressableStore:
    """SHA-256 based content-addressable storage."""

    def __init__(self, objects_dir: Path | str) -> None:
        """Initialize CAS.

        Args:
            objects_dir: Directory to store objects (will be created if needed)
        """
        self.objects_dir = Path(objects_dir)
        self.objects_dir.mkdir(parents=True, exist_ok=True)

    def compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Raw bytes to hash

        Returns:
            Lowercase hex SHA-256 digest
        """
        return hashlib.sha256(content).hexdigest()

    def store(self, content: bytes) -> str:
        """Store content and return its SHA-256 hash.

        Args:
            content: Raw bytes to store

        Returns:
            SHA-256 hash of stored content
        """
        sha256 = self.compute_hash(content)
        object_path = self.objects_dir / sha256

        # Only write if not already present (idempotent)
        if not object_path.exists():
            object_path.write_bytes(content)

        return sha256

    def retrieve(self, sha256: str) -> bytes:
        """Retrieve content by SHA-256 hash.

        Args:
            sha256: SHA-256 hash of content

        Returns:
            Raw bytes of stored content

        Raises:
            FileNotFoundError: If hash not found in store
        """
        object_path = self.objects_dir / sha256
        if not object_path.exists():
            raise FileNotFoundError(f"Object {sha256} not found in CAS")

        content = object_path.read_bytes()

        # Verify integrity
        actual_hash = self.compute_hash(content)
        if actual_hash != sha256:
            raise ValueError(
                f"Corruption detected: expected {sha256}, got {actual_hash}"
            )

        return content

    def exists(self, sha256: str) -> bool:
        """Check if object exists in store.

        Args:
            sha256: SHA-256 hash to check

        Returns:
            True if object exists, False otherwise
        """
        return (self.objects_dir / sha256).exists()
