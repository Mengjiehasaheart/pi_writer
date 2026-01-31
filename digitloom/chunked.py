import base64
import gzip
import hashlib
import json
import os
import struct
from typing import Any, Dict, Iterable, Iterator, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

from .crypto import _kdf_scrypt


_MAGIC = b"DLOOMCH1"


def _header_bytes(header: Dict[str, Any]) -> bytes:
    return json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _header_hash_hex(header: Dict[str, Any]) -> str:
    h = dict(header)
    h.pop("header_hash", None)
    hb = _header_bytes(h)
    return hashlib.sha256(hb).hexdigest()


def _encrypt_chunk(key: bytes, algorithm: str, nonce: bytes, payload: bytes, aad: bytes) -> bytes:
    if algorithm == "aes-256-gcm":
        return AESGCM(key).encrypt(nonce, payload, aad)
    return ChaCha20Poly1305(key).encrypt(nonce, payload, aad)


def _decrypt_chunk(key: bytes, algorithm: str, nonce: bytes, payload: bytes, aad: bytes) -> bytes:
    if algorithm == "aes-256-gcm":
        return AESGCM(key).decrypt(nonce, payload, aad)
    return ChaCha20Poly1305(key).decrypt(nonce, payload, aad)


class ChunkedWriter:
    def __init__(
        self,
        path: str,
        header: Dict[str, Any],
        compression: str = "none",
        encryption: str = "none",
        password: str = "",
    ):
        self.path = path
        self.compression = (compression or "none").lower().strip()
        self.encryption = (encryption or "none").lower().strip()
        self.password = password or ""
        if self.compression not in {"none", "gzip", "gz"}:
            raise ValueError("unsupported compression")
        base_header = dict(header)
        base_header["version"] = 1
        base_header["hash"] = "sha256"
        base_header["compression"] = self.compression
        base_header["encryption"] = self.encryption
        self.nonce_len = 0
        self.key = None
        self.salt = None
        if self.encryption != "none":
            if not self.password:
                raise ValueError("password is required for encryption")
            if self.encryption not in {"aes-256-gcm", "chacha20-poly1305"}:
                raise ValueError("unsupported encryption")
            self.salt = os.urandom(16)
            self.key = _kdf_scrypt(self.password, self.salt)
            self.nonce_len = 12
            base_header["kdf"] = "scrypt"
            base_header["salt"] = base64.b64encode(self.salt).decode("ascii")
            base_header["nonce_len"] = self.nonce_len
        base_header["header_hash"] = _header_hash_hex(base_header)
        self.header = base_header
        header_bytes = _header_bytes(self.header)
        self.header_hash_bytes = bytes.fromhex(self.header["header_hash"])
        self.file = open(path, "wb")
        self.file.write(_MAGIC)
        self.file.write(struct.pack(">I", len(header_bytes)))
        self.file.write(header_bytes)
        self.index = 0

    def write(self, raw: bytes):
        if not raw:
            return
        raw_len = len(raw)
        payload = raw
        if self.compression in {"gzip", "gz"}:
            payload = gzip.compress(payload)
        if self.encryption != "none":
            nonce = os.urandom(self.nonce_len)
            aad = self.header_hash_bytes + self.index.to_bytes(8, "big")
            payload = _encrypt_chunk(self.key, self.encryption, nonce, payload, aad)
        else:
            nonce = b""
        payload_len = len(payload)
        digest = hashlib.sha256(raw).digest()
        self.file.write(struct.pack(">II", raw_len, payload_len))
        self.file.write(digest)
        if nonce:
            self.file.write(nonce)
        self.file.write(payload)
        self.index += 1

    def close(self):
        if self.file:
            self.file.close()
            self.file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class ChunkedReader:
    def __init__(self, path: str, password: str = ""):
        self.path = path
        self.password = password or ""
        self.file = open(path, "rb")
        magic = self.file.read(len(_MAGIC))
        if magic != _MAGIC:
            raise ValueError("invalid magic")
        header_len_raw = self.file.read(4)
        if len(header_len_raw) != 4:
            raise ValueError("invalid header")
        header_len = struct.unpack(">I", header_len_raw)[0]
        header_bytes = self.file.read(header_len)
        if len(header_bytes) != header_len:
            raise ValueError("invalid header")
        self.header = json.loads(header_bytes.decode("utf-8"))
        computed_hash = _header_hash_hex(self.header)
        if self.header.get("header_hash") and self.header.get("header_hash") != computed_hash:
            raise ValueError("header hash mismatch")
        self.header_hash_bytes = bytes.fromhex(computed_hash)
        self.compression = (self.header.get("compression") or "none").lower().strip()
        self.encryption = (self.header.get("encryption") or "none").lower().strip()
        if self.compression not in {"none", "gzip", "gz"}:
            raise ValueError("unsupported compression")
        self.nonce_len = int(self.header.get("nonce_len") or 0)
        self.key = None
        if self.encryption != "none":
            if not self.password:
                raise ValueError("password is required for decryption")
            salt_b64 = self.header.get("salt")
            if not salt_b64:
                raise ValueError("missing salt")
            salt = base64.b64decode(salt_b64.encode("ascii"))
            self.key = _kdf_scrypt(self.password, salt)
        self.index = 0

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        header_raw = self.file.read(8)
        if not header_raw:
            raise StopIteration
        if len(header_raw) != 8:
            raise ValueError("invalid chunk header")
        raw_len, payload_len = struct.unpack(">II", header_raw)
        digest = self.file.read(32)
        if len(digest) != 32:
            raise ValueError("invalid chunk hash")
        if self.encryption != "none":
            nonce = self.file.read(self.nonce_len)
            if len(nonce) != self.nonce_len:
                raise ValueError("invalid nonce")
        else:
            nonce = b""
        payload = self.file.read(payload_len)
        if len(payload) != payload_len:
            raise ValueError("invalid chunk payload")
        data = payload
        if self.encryption != "none":
            aad = self.header_hash_bytes + self.index.to_bytes(8, "big")
            data = _decrypt_chunk(self.key, self.encryption, nonce, data, aad)
        if self.compression in {"gzip", "gz"}:
            data = gzip.decompress(data)
        if len(data) != raw_len:
            raise ValueError("invalid chunk length")
        if hashlib.sha256(data).digest() != digest:
            raise ValueError("chunk hash mismatch")
        self.index += 1
        return data

    def close(self):
        if self.file:
            self.file.close()
            self.file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
