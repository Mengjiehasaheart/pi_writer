import json
import os
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


_MAGIC = b"DLOOM1"
_ALG_AESGCM = 1
_ALG_CHACHA20 = 2


def _kdf_scrypt(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    return kdf.derive(password.encode("utf-8"))


def encrypt_blob_v1(plaintext: bytes, password: str, algorithm: str, aad: Dict[str, Any]) -> bytes:
    if not password:
        raise ValueError("password is required")
    algorithm = algorithm.lower().strip()
    if algorithm not in {"aes-256-gcm", "chacha20-poly1305"}:
        raise ValueError("unsupported algorithm")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _kdf_scrypt(password, salt)
    meta = dict(aad)
    meta["kdf"] = "scrypt"
    meta["alg"] = algorithm
    meta_bytes = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(meta_bytes) > 2**32 - 1:
        raise ValueError("aad too large")
    if algorithm == "aes-256-gcm":
        alg_id = _ALG_AESGCM
        ct = AESGCM(key).encrypt(nonce, plaintext, meta_bytes)
    else:
        alg_id = _ALG_CHACHA20
        ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, meta_bytes)
    return b"".join(
        [
            _MAGIC,
            bytes([alg_id]),
            salt,
            nonce,
            len(meta_bytes).to_bytes(4, "big"),
            meta_bytes,
            ct,
        ]
    )


def decrypt_blob_v1(blob: bytes, password: str) -> Tuple[bytes, Dict[str, Any]]:
    if not password:
        raise ValueError("password is required")
    if len(blob) < len(_MAGIC) + 1 + 16 + 12 + 4:
        raise ValueError("invalid blob")
    if blob[: len(_MAGIC)] != _MAGIC:
        raise ValueError("invalid magic")
    pos = len(_MAGIC)
    alg_id = blob[pos]
    pos += 1
    salt = blob[pos : pos + 16]
    pos += 16
    nonce = blob[pos : pos + 12]
    pos += 12
    meta_len = int.from_bytes(blob[pos : pos + 4], "big")
    pos += 4
    meta_bytes = blob[pos : pos + meta_len]
    pos += meta_len
    ct = blob[pos:]
    key = _kdf_scrypt(password, salt)
    if alg_id == _ALG_AESGCM:
        pt = AESGCM(key).decrypt(nonce, ct, meta_bytes)
    elif alg_id == _ALG_CHACHA20:
        pt = ChaCha20Poly1305(key).decrypt(nonce, ct, meta_bytes)
    else:
        raise ValueError("unsupported algorithm id")
    meta = json.loads(meta_bytes.decode("utf-8"))
    return pt, meta
