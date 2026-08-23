"""Model checkpoint supply chain (control C-34, threat T-05).

A ``.pt``/``.bin``/``.ckpt`` checkpoint is a **Python pickle**. ``torch.load`` on an
untrusted one is arbitrary code execution on whatever machine performs inference -- not
a theoretical risk but the documented behaviour of the format.

This module makes the safe path the only path:

* only ``.safetensors`` files may be loaded -- the format is a length-prefixed header
  plus raw tensor bytes, with no code execution path;
* every checkpoint must be pinned by SHA-256 and verified before use;
* every checkpoint must be pinned to a repository revision, so "latest" cannot silently
  become something else tomorrow.

It deliberately does not import torch: the API must never gain that dependency
(ADR-0007 / C-45), and verification is pure file I/O.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The only extension this project will load.
ALLOWED_SUFFIX: Final[str] = ".safetensors"

#: Formats that are pickles, or contain them. Loading any of these is code execution.
PICKLE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".pt", ".pth", ".bin", ".ckpt", ".pkl", ".pickle", ".joblib", ".npy", ".npz"}
)

_CHUNK: Final[int] = 1024 * 1024


class UnsafeCheckpointError(Exception):
    """A checkpoint failed a supply-chain check and must not be loaded."""


@dataclass(frozen=True)
class PinnedModel:
    """A model pinned by both content hash and source revision."""

    name: str
    filename: str
    sha256: str
    revision: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64 or not all(c in "0123456789abcdef" for c in self.sha256):
            raise ValueError(f"{self.name}: sha256 must be a 64-character hex digest")
        if not self.revision:
            raise ValueError(f"{self.name}: revision must be pinned, never floating")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def assert_safe_format(path: Path) -> None:
    """Reject anything that is not safetensors, naming pickles explicitly."""
    suffix = path.suffix.lower()
    if suffix in PICKLE_SUFFIXES:
        raise UnsafeCheckpointError(
            f"{path.name}: {suffix} is a pickle format. Loading it is arbitrary code "
            "execution (control C-34, threat T-05). Convert to .safetensors."
        )
    if suffix != ALLOWED_SUFFIX:
        raise UnsafeCheckpointError(
            f"{path.name}: only {ALLOWED_SUFFIX} checkpoints may be loaded, got {suffix!r}"
        )


def verify_checkpoint(path: Path, pinned: PinnedModel) -> None:
    """Full pre-load check: format, existence, then content hash.

    Raises :class:`UnsafeCheckpointError` on any failure. There is no override flag; a
    checkpoint that does not verify does not get loaded.
    """
    assert_safe_format(path)
    if not path.is_file():
        raise UnsafeCheckpointError(f"{path}: checkpoint not found")
    actual = sha256_file(path)
    if actual != pinned.sha256:
        raise UnsafeCheckpointError(
            f"{path.name}: checksum mismatch. Expected {pinned.sha256[:16]}..., "
            f"got {actual[:16]}.... Refusing to load a checkpoint that changed."
        )


#: The model registry. Every entry must carry a real hash and a real revision before it
#: is used. Empty today because no checkpoint has been obtained -- see docs/STATUS.md.
MODEL_REGISTRY: Final[dict[str, PinnedModel]] = {}
