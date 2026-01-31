import gzip
import json
import os
import subprocess
import sys
import time
import webbrowser

import click
from mpmath import mp

from .bbp import pi_hex_digits
from .chunked import ChunkedReader, ChunkedWriter
from .chudnovsky import chudnovsky_pi_decimal_string
from .constants import compute_precision, constants_map, integer_to_base, pi_digits_spigot, render_in_base, safe_custom
from .crypto import decrypt_blob_v1, encrypt_blob_v1
from .formats import serialize_payload
from .pipeline import apply_compression
from .streaming import display_prefix, iter_fractional_chunks
from .verify import extract_fractional_digits, read_fractional_digits_from_chunked, read_fractional_digits_from_text, verify_fractional_digits


def _final_filename(stem: str, fmt: str, compression_suffix: str, encrypted: bool) -> str:
    name = f"{stem}.{fmt}{compression_suffix}"
    if encrypted:
        name = name + ".enc"
    return name


def _run_app(host: str, port: int, open_browser: bool):
    url = f"http://{host}:{port}"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        os.path.join(os.path.dirname(__file__), "streamlit_app.py"),
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]
    proc = subprocess.Popen(cmd)
    if open_browser:
        for _ in range(60):
            time.sleep(0.2)
            try:
                webbrowser.open(url)
                break
            except Exception:
                pass
    raise SystemExit(proc.wait())


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


@main.command()
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=8501, show_default=True, type=int)
@click.option("--open/--no-open", default=True, show_default=True)
def app(host: str, port: int, open: bool):
    _run_app(host, port, open)


@main.command()
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=8501, show_default=True, type=int)
@click.option("--open/--no-open", default=True, show_default=True)
def start(host: str, port: int, open: bool):
    _run_app(host, port, open)


@main.command()
@click.option("--constant", "constant_name", default="Pi (π)", show_default=True)
@click.option("--expr", default="", show_default=True)
@click.option("--digits", default=1000, show_default=True, type=int)
@click.option("--base", default=10, show_default=True, type=int)
@click.option("--engine", type=click.Choice(["mpmath-fast", "mpmath-exact", "chudnovsky"], case_sensitive=False), default="mpmath-fast", show_default=True)
@click.option("--workers", default=1, show_default=True, type=int)
@click.option("--format", "fmt", type=click.Choice(["txt", "json", "csv", "tsv", "ndjson", "bin", "sqlite", "zip", "dloom"], case_sensitive=False), default="txt", show_default=True)
@click.option("--binary-mode", type=click.Choice(["ASCII digits", "Packed BCD"], case_sensitive=False), default="ASCII digits", show_default=True)
@click.option("--compression", type=click.Choice(["none", "gzip"], case_sensitive=False), default="none", show_default=True)
@click.option("--stream/--no-stream", default=False, show_default=True)
@click.option("--chunk-size", default=10000, show_default=True, type=int)
@click.option("--encrypt", is_flag=True)
@click.option("--password", default="", show_default=False)
@click.option("--encryption", type=click.Choice(["aes-256-gcm", "chacha20-poly1305"], case_sensitive=False), default="aes-256-gcm", show_default=True)
@click.option("--label/--no-label", default=True, show_default=True)
@click.option("--verify/--no-verify", default=False, show_default=True)
@click.option("--verify-samples", default=1000, show_default=True, type=int)
@click.option("--out", "out_path", default="digits", show_default=True)
def generate(
    constant_name: str,
    expr: str,
    digits: int,
    base: int,
    engine: str,
    workers: int,
    fmt: str,
    binary_mode: str,
    compression: str,
    stream: bool,
    chunk_size: int,
    encrypt: bool,
    password: str,
    encryption: str,
    label: bool,
    verify: bool,
    verify_samples: int,
    out_path: str,
):
    engine = engine.lower().strip()
    fmt = fmt.lower().strip()
    compression = (compression or "none").lower().strip()
    if fmt == "dloom":
        stream = True
    if fmt == "bin" and binary_mode.lower().strip() == "packed bcd":
        label = False
    if chunk_size < 1:
        raise click.ClickException("--chunk-size must be >= 1")
    if stream and fmt not in {"txt", "dloom"}:
        raise click.ClickException("stream mode supports only txt or dloom formats")
    if stream and fmt == "txt" and encrypt:
        raise click.ClickException("streamed txt output does not support encryption")
    if stream and engine == "chudnovsky":
        raise click.ClickException("stream mode does not support chudnovsky")
    guard = 60 if verify else 30
    p = compute_precision(digits, base, guard=guard)
    mp.dps = p
    c = constants_map()
    if constant_name not in c:
        raise click.ClickException("unknown constant")
    if constant_name == "Custom":
        if not expr:
            raise click.ClickException("--expr required for Custom")
        val = safe_custom(expr, p)
        name_for_label = "Custom"
    else:
        val = c[constant_name]()
        name_for_label = constant_name.split(" ")[0]
    label_prefix = (name_for_label + " = ") if label else ""
    label_map = {10: "", 16: "0x"}
    base_prefix = label_map.get(base, "")
    if stream:
        if out_path.lower().endswith("." + fmt):
            stem = out_path[: -(len(fmt) + 1)]
        else:
            stem = out_path
        suffix = ".gz" if compression in {"gzip", "gz"} and fmt == "txt" else ""
        encrypted = bool(encrypt) and fmt == "dloom"
        filename = _final_filename(stem, fmt, suffix, encrypted)
        if fmt == "txt":
            prefix = display_prefix(label_prefix, base_prefix, int(mp.floor(val)), base)
            if compression in {"gzip", "gz"}:
                out = gzip.open(filename, "wb")
            else:
                out = open(filename, "wb")
            with out as f:
                f.write(prefix.encode("utf-8"))
                for chunk in iter_fractional_chunks(val, digits, base, chunk_size):
                    f.write(chunk.encode("ascii"))
        else:
            header = {
                "constant": constant_name,
                "base": int(base),
                "digits": int(digits),
                "engine": engine,
                "format": fmt,
                "int_part": integer_to_base(int(mp.floor(val)), base),
                "label_prefix": label_prefix,
                "base_prefix": base_prefix,
                "decimal": ".",
                "chunk_size": int(chunk_size),
            }
            enc_alg = encryption if encrypt else "none"
            with ChunkedWriter(filename, header, compression=compression, encryption=enc_alg, password=password) as writer:
                for chunk in iter_fractional_chunks(val, digits, base, chunk_size):
                    writer.write(chunk.encode("ascii"))
        if verify:
            if fmt == "txt":
                fractional = read_fractional_digits_from_text(filename, verify_samples)
            else:
                fractional = read_fractional_digits_from_chunked(filename, verify_samples, password=password if encrypt else "")
            ok, kind = verify_fractional_digits(constant_name, expr, base, verify_samples, fractional)
            if not ok:
                raise click.ClickException(f"verification failed ({kind})")
        click.echo(filename)
        return
    if engine == "chudnovsky":
        if constant_name != "Pi (π)" or base != 10:
            raise click.ClickException("chudnovsky engine supports only Pi base 10")
        s = chudnovsky_pi_decimal_string(digits, workers=workers)
    else:
        method = "Fast" if engine == "mpmath-fast" else "Exact"
        s = render_in_base(val, digits, base, method)
    display = label_prefix + (base_prefix + s)
    meta = {"constant": constant_name, "base": base, "digits": digits, "engine": engine, "format": fmt}
    payload, mime = serialize_payload(display, fmt, meta, binary_mode=binary_mode)
    payload, suffix = apply_compression(payload, compression)
    encrypted = False
    if encrypt:
        encrypted = True
        payload = encrypt_blob_v1(payload, password=password, algorithm=encryption, aad={"mime": mime, "format": fmt, "compression": compression})
        mime = "application/octet-stream"
    if out_path.lower().endswith("." + fmt):
        stem = out_path[: -(len(fmt) + 1)]
    else:
        stem = out_path
    filename = _final_filename(stem, fmt, suffix, encrypted)
    with open(filename, "wb") as f:
        f.write(payload)
    if verify:
        fractional = extract_fractional_digits(display)
        ok, kind = verify_fractional_digits(constant_name, expr, base, verify_samples, fractional)
        if not ok:
            raise click.ClickException(f"verification failed ({kind})")
    click.echo(filename)


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--password", required=True)
@click.option("--out", "out_path", default="", show_default=True)
def decrypt(path: str, password: str, out_path: str):
    with open(path, "rb") as f:
        blob = f.read()
    pt, meta = decrypt_blob_v1(blob, password=password)
    if out_path:
        out = out_path
    else:
        out = path + ".dec"
    with open(out, "wb") as f:
        f.write(pt)
    click.echo(out)
    click.echo(json.dumps(meta, ensure_ascii=False))


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--password", default="", show_default=True)
@click.option("--out", "out_path", default="", show_default=True)
def unpack(path: str, password: str, out_path: str):
    with ChunkedReader(path, password=password) as reader:
        header = reader.header
        prefix = f"{header.get('label_prefix','')}{header.get('base_prefix','')}{header.get('int_part','')}."
        if out_path:
            out = out_path
        else:
            out = path + ".txt"
        with open(out, "wb") as f:
            f.write(prefix.encode("utf-8"))
            for chunk in reader:
                f.write(chunk)
    click.echo(out)
    click.echo(json.dumps(header, ensure_ascii=False))


@main.command()
@click.option("--start", default=0, show_default=True, type=int)
@click.option("--count", default=64, show_default=True, type=int)
@click.option("--out", "out_path", default="", show_default=True)
def pi_hex(start: int, count: int, out_path: str):
    s = pi_hex_digits(start, count)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(s)
        click.echo(out_path)
    else:
        click.echo(s)


@main.command()
@click.option("--digits", default=1_000_000, show_default=True, type=int)
@click.option("--infinite", is_flag=True)
@click.option("--chunk", "chunk_size", default=1000, show_default=True, type=int)
@click.option("--out", "out_path", default="pi_stream.txt", show_default=True)
@click.option("--newline/--no-newline", default=False, show_default=True)
def stream_pi(digits: int, infinite: bool, chunk_size: int, out_path: str, newline: bool):
    digits = int(digits)
    chunk_size = int(chunk_size)
    if chunk_size < 1:
        raise click.ClickException("--chunk must be >= 1")
    if not infinite and digits < 1:
        raise click.ClickException("--digits must be >= 1")
    g = pi_digits_spigot()
    first = next(g)
    written = 0
    with open(out_path, "wb") as f:
        f.write(f"{first}.".encode("ascii"))
        try:
            while infinite or written < digits - 1:
                take = chunk_size if infinite else min(chunk_size, digits - 1 - written)
                chunk = "".join(str(next(g)) for _ in range(take))
                if newline:
                    chunk = chunk + "\n"
                f.write(chunk.encode("ascii"))
                written += take
        except KeyboardInterrupt:
            pass
    click.echo(out_path)
