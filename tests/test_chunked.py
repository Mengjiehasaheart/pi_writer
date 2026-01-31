import os
import tempfile

from digitloom.chunked import ChunkedReader, ChunkedWriter


def test_chunked_roundtrip_plain():
    header = {
        "constant": "Pi (π)",
        "base": 10,
        "digits": 4,
        "engine": "mpmath-fast",
        "format": "dloom",
        "int_part": "3",
        "label_prefix": "Pi = ",
        "base_prefix": "",
        "decimal": ".",
        "chunk_size": 2,
    }
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "digits.dloom")
        with ChunkedWriter(path, header, compression="none", encryption="none") as w:
            w.write(b"14")
            w.write(b"15")
        with ChunkedReader(path) as r:
            out = b"".join(list(r))
            assert out == b"1415"
            assert r.header["int_part"] == "3"


def test_chunked_roundtrip_encrypted():
    header = {
        "constant": "Pi (π)",
        "base": 10,
        "digits": 4,
        "engine": "mpmath-fast",
        "format": "dloom",
        "int_part": "3",
        "label_prefix": "",
        "base_prefix": "",
        "decimal": ".",
        "chunk_size": 2,
    }
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "digits.dloom")
        with ChunkedWriter(path, header, compression="gzip", encryption="aes-256-gcm", password="pw") as w:
            w.write(b"14")
            w.write(b"15")
        with ChunkedReader(path, password="pw") as r:
            out = b"".join(list(r))
            assert out == b"1415"
