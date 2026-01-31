from digitloom.crypto import decrypt_blob_v1, encrypt_blob_v1


def test_encrypt_decrypt_aesgcm_roundtrip():
    pt = b"hello"
    blob = encrypt_blob_v1(pt, password="pw", algorithm="aes-256-gcm", aad={"a": 1})
    out, meta = decrypt_blob_v1(blob, password="pw")
    assert out == pt
    assert meta["a"] == 1
    assert meta["alg"] == "aes-256-gcm"
    assert meta["kdf"] == "scrypt"


def test_encrypt_decrypt_chacha_roundtrip():
    pt = b"hello"
    blob = encrypt_blob_v1(pt, password="pw", algorithm="chacha20-poly1305", aad={"a": 1})
    out, meta = decrypt_blob_v1(blob, password="pw")
    assert out == pt
    assert meta["alg"] == "chacha20-poly1305"
