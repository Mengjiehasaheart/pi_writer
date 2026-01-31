import io
import json
import os
import sqlite3
import tempfile
import zipfile

from digitloom.formats import serialize_payload


def test_serialize_txt():
    b, mime = serialize_payload("Pi = 3.14", "txt", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime == "text/plain"
    assert b == "Pi = 3.14".encode("utf-8")


def test_serialize_json():
    b, mime = serialize_payload("3.14", "json", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime == "application/json"
    payload = json.loads(b.decode("utf-8"))
    assert payload["value"] == "3.14"


def test_serialize_csv_tsv():
    b, mime = serialize_payload("3.14", "csv", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime == "text/csv"
    assert b.decode("utf-8").splitlines()[0] == "constant,base,digits,value"
    b2, mime2 = serialize_payload("3.14", "tsv", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime2 == "text/tab-separated-values"
    assert "\t" in b2.decode("utf-8").splitlines()[0]


def test_serialize_ndjson():
    b, mime = serialize_payload("3.14", "ndjson", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime == "application/x-ndjson"
    payload = json.loads(b.decode("utf-8"))
    assert payload["value"] == "3.14"


def test_serialize_bin_ascii():
    b, mime = serialize_payload("3.14", "bin", {"constant": "Pi (π)", "base": 10, "digits": 2}, binary_mode="ASCII digits")
    assert mime == "application/octet-stream"
    assert b == b"3.14"


def test_serialize_bin_packed():
    b, _ = serialize_payload("Pi = 31.41", "bin", {"constant": "Pi (π)", "base": 10, "digits": 2}, binary_mode="Packed BCD")
    assert len(b) == 2
    assert b[0] == 0x31
    assert b[1] == 0x41


def test_serialize_sqlite():
    b, mime = serialize_payload("3.14", "sqlite", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime == "application/vnd.sqlite3"
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        path = tf.name
        tf.write(b)
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("select constant, base, digits, value from digits order by id asc limit 1")
        row = cur.fetchone()
        assert row[0] == "Pi (π)"
        assert row[1] == 10
        assert row[2] == 2
        assert row[3] == "3.14"
        conn.close()
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def test_serialize_zip():
    b, mime = serialize_payload("3.14", "zip", {"constant": "Pi (π)", "base": 10, "digits": 2})
    assert mime == "application/zip"
    with zipfile.ZipFile(io.BytesIO(b), "r") as zf:
        names = set(zf.namelist())
        assert "meta.json" in names
        assert "digits.txt" in names
