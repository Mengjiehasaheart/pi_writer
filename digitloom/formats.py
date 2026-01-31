import os
import io
import json
import sqlite3
import tempfile
import zipfile
from typing import Dict, Tuple


def _packed_nibbles_from_digits(s: str) -> bytes:
    raw = []
    for ch in s:
        if ch == ".":
            continue
        d = ord(ch)
        if 48 <= d <= 57:
            raw.append(d - 48)
        elif 97 <= d <= 102:
            raw.append(d - 87)
        elif 65 <= d <= 70:
            raw.append(d - 55)
    out = bytearray()
    i = 0
    while i < len(raw):
        hi = raw[i]
        lo = raw[i + 1] if i + 1 < len(raw) else 0
        out.append(((hi & 0x0F) << 4) | (lo & 0x0F))
        i += 2
    return bytes(out)


def serialize_payload(value: str, fmt: str, meta: Dict, binary_mode: str = "ASCII digits") -> Tuple[bytes, str]:
    fmt = fmt.lower().strip()
    if fmt == "txt":
        return value.encode("utf-8"), "text/plain"
    if fmt == "json":
        payload = dict(meta)
        payload["value"] = value
        return (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            "application/json",
        )
    if fmt in {"csv", "tsv"}:
        sep = "," if fmt == "csv" else "\t"
        header = ["constant", "base", "digits", "value"]
        row = [str(meta.get("constant")), str(meta.get("base")), str(meta.get("digits")), value]
        out = sep.join(header) + "\n" + sep.join(row) + "\n"
        mime = "text/csv" if fmt == "csv" else "text/tab-separated-values"
        return out.encode("utf-8"), mime
    if fmt == "ndjson":
        payload = dict(meta)
        payload["value"] = value
        out = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        return out.encode("utf-8"), "application/x-ndjson"
    if fmt == "bin":
        if binary_mode.lower().strip() == "packed bcd":
            return _packed_nibbles_from_digits(value), "application/octet-stream"
        return value.encode("ascii", errors="ignore"), "application/octet-stream"
    if fmt == "sqlite":
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
            tmp = tf.name
        try:
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            cur.execute(
                "create table if not exists digits (id integer primary key, constant text, base integer, digits integer, value text)"
            )
            cur.execute(
                "insert into digits(constant,base,digits,value) values(?,?,?,?)",
                (meta.get("constant"), int(meta.get("base")), int(meta.get("digits")), value),
            )
            conn.commit()
            conn.close()
            with open(tmp, "rb") as f:
                return f.read(), "application/vnd.sqlite3"
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
    if fmt == "zip":
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
            zf.writestr("digits.txt", value)
        return mem.getvalue(), "application/zip"
    return value.encode("utf-8"), "application/octet-stream"
