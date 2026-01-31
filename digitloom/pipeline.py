import gzip
from typing import Tuple


def apply_compression(payload: bytes, compression: str) -> Tuple[bytes, str]:
    compression = (compression or "none").lower().strip()
    if compression == "none":
        return payload, ""
    if compression in {"gzip", "gz"}:
        return gzip.compress(payload), ".gz"
    raise ValueError("unsupported compression")
