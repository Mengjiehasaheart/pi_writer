import gzip
import os
import subprocess
import sys
import time
import math

import streamlit as st
from mpmath import mp

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from digitloom.bbp import pi_hex_digits
from digitloom.chunked import ChunkedWriter
from digitloom.chudnovsky import chudnovsky_pi_decimal_string
from digitloom.constants import compute_precision, constants_map, integer_to_base, render_in_base, safe_custom
from digitloom.crypto import encrypt_blob_v1
from digitloom.formats import serialize_payload
from digitloom.pipeline import apply_compression
from digitloom.streaming import display_prefix, iter_fractional_chunks
from digitloom.verify import extract_fractional_digits, read_fractional_digits_from_chunked, read_fractional_digits_from_text, verify_fractional_digits


def _style():
    st.markdown(
        """
        <style>
        :root {--brand:#0ea5e9;--ink:#0b132b;--muted:#6b7280;--bg0:#0b132b;--bg1:#16213e;--bg2:#1f2937;--fg:#e5e7eb}
        .stApp {background: radial-gradient(60% 80% at 20% 10%, rgba(14,165,233,.15), transparent 40%), radial-gradient(60% 80% at 100% 0%, rgba(99,102,241,.15), transparent 40%), linear-gradient(180deg, var(--bg0), var(--bg1))}
        .title-wrap {padding: 24px 20px 10px; border-bottom: 1px solid rgba(255,255,255,.08); margin-bottom: 12px}
        .title {font-weight: 800; font-size: 28px; letter-spacing: .2px; color: white}
        .subtitle {color: var(--fg); opacity:.8; margin-top: 6px}
        .chip {display:inline-block; padding:6px 10px; border-radius:20px; background:rgba(14,165,233,.15); color:#7dd3fc; font-size:12px; margin-left:8px}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _header():
    st.markdown(
        """
        <div class="title-wrap">
          <div class="title">DigitLoom<span class="chip">by Mengjie Fan</span></div>
          <div class="subtitle">constants into artifacts, with streaming, verification, and chunked output.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _final_name(stem: str, fmt: str, compression_suffix: str, encrypted: bool) -> str:
    name = f"{stem}.{fmt}{compression_suffix}"
    if encrypted:
        name = name + ".enc"
    return name


def _theoretical_bits(digits: int, base: int) -> int:
    return int(int(digits) * math.log2(int(base)))


def _cli_command(
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
    encryption: str,
    label: bool,
    verify: bool,
    verify_samples: int,
    out_path: str,
):
    parts = ["python3", "-m", "digitloom", "generate"]
    parts += ["--constant", constant_name]
    if constant_name == "Custom":
        parts += ["--expr", expr]
    parts += ["--digits", str(int(digits))]
    parts += ["--base", str(int(base))]
    parts += ["--engine", engine]
    parts += ["--workers", str(int(workers))]
    parts += ["--format", fmt]
    if fmt == "bin":
        parts += ["--binary-mode", binary_mode]
    parts += ["--compression", compression]
    if stream:
        parts += ["--stream", "--chunk-size", str(int(chunk_size))]
    if encrypt:
        parts += ["--encrypt", "--encryption", encryption]
    if not label:
        parts += ["--no-label"]
    if verify:
        parts += ["--verify", "--verify-samples", str(int(verify_samples))]
    parts += ["--out", out_path]
    return " ".join(parts)


def _apply_preset(preset: str):
    presets = {
        "1K digits (txt)": {
            "digits": 1000,
            "base": 10,
            "engine": "mpmath-fast",
            "fmt": "txt",
            "compression": "none",
            "output_mode": "Download",
        },
        "1M digits (dloom)": {
            "digits": 1_000_000,
            "base": 10,
            "engine": "mpmath-exact",
            "fmt": "dloom",
            "compression": "none",
            "output_mode": "Stream to file",
            "chunk_size": 10000,
            "verify": True,
            "verify_samples": 2000,
        },
        "e 10K digits (txt)": {
            "constant": "Euler's e",
            "digits": 10000,
            "base": 10,
            "engine": "mpmath-exact",
            "fmt": "txt",
            "compression": "none",
            "output_mode": "Download",
        },
        "φ 2K digits (hex)": {
            "constant": "Golden ratio (φ)",
            "digits": 2000,
            "base": 16,
            "engine": "mpmath-exact",
            "fmt": "txt",
            "compression": "none",
            "output_mode": "Download",
        },
        "π hex window (BBP)": {
            "mode": "π hex extract (BBP)",
        },
        "π spigot stream": {
            "mode": "π spigot stream",
        },
    }
    if preset not in presets:
        return
    for k, v in presets[preset].items():
        st.session_state[k] = v


def main():
    st.set_page_config(page_title="DigitLoom", page_icon="🧮", layout="wide")
    _style()
    _header()
    if "history" not in st.session_state:
        st.session_state.history = []
    if "mode" not in st.session_state:
        st.session_state.mode = "Generate / Export"
    c = constants_map()
    with st.sidebar:
        mode_options = ["Generate / Export", "π spigot stream", "π hex extract (BBP)"]
        mode_map = {"Generate": "Generate / Export", "Stream π to file": "π spigot stream", "π hex extract": "π hex extract (BBP)"}
        current_mode = mode_map.get(st.session_state.mode, st.session_state.mode)
        if current_mode not in mode_options:
            current_mode = mode_options[0]
        mode = st.radio("Mode", options=mode_options, index=mode_options.index(current_mode), key="mode")
        preset = st.selectbox("Presets", options=["", "1K digits (txt)", "1M digits (dloom)", "e 10K digits (txt)", "φ 2K digits (hex)", "π hex window (BBP)", "π spigot stream"], index=0)
        if st.button("Apply preset", use_container_width=True) and preset:
            _apply_preset(preset)
        st.divider()
        if mode == "π spigot stream":
            st.caption("This mode streams π only. For other constants, use Generate / Export with Stream to file.")
            if "pi_stream_proc" not in st.session_state:
                st.session_state.pi_stream_proc = None
            if st.session_state.pi_stream_proc is not None and st.session_state.pi_stream_proc.poll() is not None:
                st.session_state.pi_stream_proc = None
            out_path = st.text_input("Output path", value=os.path.join(os.getcwd(), "pi_stream.txt"))
            chunk_size = st.number_input("Chunk size", min_value=1, max_value=1_000_000, value=5000, step=1000)
            newline = st.checkbox("Newline per chunk", value=False)
            infinite = st.checkbox("Infinite", value=True)
            digits_limit = st.number_input("Digits (if not infinite)", min_value=1, max_value=100_000_000, value=1_000_000, step=100_000, disabled=infinite)
            colS1, colS2 = st.columns(2)
            with colS1:
                start = st.button("Start stream", type="primary", use_container_width=True, disabled=st.session_state.pi_stream_proc is not None)
            with colS2:
                stop = st.button("Stop stream", use_container_width=True, disabled=st.session_state.pi_stream_proc is None)
            if start:
                cmd = [
                    sys.executable,
                    "-m",
                    "digitloom",
                    "stream-pi",
                    "--out",
                    out_path,
                    "--chunk",
                    str(int(chunk_size)),
                ]
                if newline:
                    cmd.append("--newline")
                if infinite:
                    cmd.append("--infinite")
                else:
                    cmd.extend(["--digits", str(int(digits_limit))])
                st.session_state.pi_stream_proc = subprocess.Popen(cmd)
            if stop and st.session_state.pi_stream_proc is not None:
                st.session_state.pi_stream_proc.terminate()
                try:
                    st.session_state.pi_stream_proc.wait(timeout=5)
                except Exception:
                    pass
                st.session_state.pi_stream_proc = None
            if st.session_state.pi_stream_proc is not None:
                st.info(f"Streaming... PID {st.session_state.pi_stream_proc.pid}")
            else:
                st.caption("Streaming runs in a separate process so the UI stays responsive.")
            return
        if mode == "π hex extract (BBP)":
            start = st.number_input("Hex digit start (after point)", min_value=0, max_value=10_000_000, value=0, step=1)
            count = st.number_input("Count", min_value=1, max_value=2000, value=64, step=1)
            if st.button("Extract", type="primary", use_container_width=True):
                s = pi_hex_digits(int(start), int(count))
                st.code(s, language="text")
            return
        output_mode = st.radio("Output", options=["Download", "Stream to file"], index=0, key="output_mode")
        base = st.selectbox("Base", options=[10, 16], index=0, key="base")
        engine = st.selectbox("Engine", options=["mpmath-fast", "mpmath-exact", "chudnovsky"], index=0, key="engine")
        workers = st.slider("CPU workers", min_value=1, max_value=os.cpu_count() or 8, value=1, key="workers")
        name = st.selectbox("Constant", options=list(c.keys()), index=0, key="constant")
        expr = ""
        if name == "Custom":
            expr = st.text_input("Expression", value=st.session_state.get("expr", "sin(1)+cos(1)+sqrt(2)/7"), key="expr")
        digits = st.number_input("Digits after point", min_value=1, max_value=2_000_000, value=st.session_state.get("digits", 1000), step=1000, key="digits")
        fmt_options = ["txt", "json", "csv", "tsv", "ndjson", "bin", "sqlite", "zip"] if output_mode == "Download" else ["txt", "dloom"]
        fmt = st.selectbox("Format", options=fmt_options, index=0, key="fmt")
        binary_mode = "ASCII digits"
        packed = False
        if fmt == "bin":
            binary_mode = st.selectbox("Binary encoding", options=["ASCII digits", "Packed BCD"], index=0, key="binary_mode")
            packed = binary_mode == "Packed BCD"
        compression = st.selectbox("Compression", options=["none", "gzip"], index=0, key="compression")
        encrypt = st.checkbox("Encrypt output", value=st.session_state.get("encrypt", False), key="encrypt")
        encryption = st.selectbox("Encryption", options=["aes-256-gcm", "chacha20-poly1305"], index=0, disabled=not encrypt, key="encryption")
        password = st.text_input("Password", value=st.session_state.get("password", ""), type="password", disabled=not encrypt, key="password")
        add_label = False if packed else st.checkbox("Include label prefix", value=st.session_state.get("label", True), key="label")
        filename = st.text_input("Filename stem", value=st.session_state.get("out", "digits"), key="out")
        advanced = st.expander("Advanced")
        with advanced:
            verify = st.checkbox("Research-grade verification", value=st.session_state.get("verify", False), key="verify")
            verify_samples = st.number_input("Verify digits", min_value=0, max_value=2_000_000, value=st.session_state.get("verify_samples", 1000), step=1000, key="verify_samples")
            chunk_size = st.number_input("Chunk size", min_value=1, max_value=1_000_000, value=st.session_state.get("chunk_size", 10000), step=1000, key="chunk_size")
        if output_mode == "Stream to file" and fmt == "txt" and encrypt:
            st.warning("Streaming txt cannot be encrypted; use dloom for encrypted streaming.")
        if output_mode == "Stream to file" and engine == "chudnovsky":
            st.warning("Streaming mode does not support chudnovsky.")
        large_warning = digits >= 1_000_000 and output_mode == "Download"
        confirm_large = True
        if large_warning:
            confirm_large = st.checkbox("I understand this may be large and slow", value=False)
        generate = st.button("Generate", type="primary", use_container_width=True, disabled=large_warning and not confirm_large)

    if not generate:
        st.caption("Tip: use Stream to file for very large outputs and dloom for chunked artifacts.")
        if st.session_state.history:
            st.subheader("Recent runs")
            for item in st.session_state.history[:5]:
                st.write(item)
        return

    t0 = time.perf_counter()
    guard = 60 if verify else 30
    p = compute_precision(int(digits), int(base), guard=guard)
    mp.dps = p
    if engine == "chudnovsky":
        if name != "Pi (π)" or base != 10 or output_mode == "Stream to file":
            st.error("Chudnovsky supports only Pi (π) in base 10 and not in streaming mode.")
            return
        s = chudnovsky_pi_decimal_string(int(digits), workers=int(workers))
        label_name = "Pi"
    else:
        if name == "Custom":
            val = safe_custom(expr, p)
            label_name = "Custom"
        else:
            val = c[name]()
            label_name = name.split(" ")[0]
    label_map = {10: "", 16: "0x"}
    base_prefix = label_map[base]
    label_prefix = (label_name + " = ") if add_label else ""

    if output_mode == "Stream to file":
        if fmt == "txt" and encrypt:
            st.error("Streaming txt cannot be encrypted; use dloom.")
            return
        if fmt == "dloom" and encrypt and not password:
            st.error("Password is required for encryption.")
            return
        suffix = ".gz" if compression in {"gzip", "gz"} and fmt == "txt" else ""
        encrypted = bool(encrypt) and fmt == "dloom"
        out_path = os.path.join(os.getcwd(), _final_name(filename, fmt, suffix, encrypted))
        status = st.empty()
        progress = st.progress(0)
        if fmt == "txt":
            prefix = display_prefix(label_prefix, base_prefix, int(mp.floor(val)), base)
            if compression in {"gzip", "gz"}:
                out = gzip.open(out_path, "wb")
            else:
                out = open(out_path, "wb")
            written = 0
            with out as f:
                f.write(prefix.encode("utf-8"))
                for chunk in iter_fractional_chunks(val, int(digits), int(base), int(chunk_size)):
                    f.write(chunk.encode("ascii"))
                    written += len(chunk)
                    progress.progress(min(1.0, written / max(1, int(digits))))
            status.success(f"Saved to {out_path}")
        else:
            header = {
                "constant": name,
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
            written = 0
            with ChunkedWriter(out_path, header, compression=compression, encryption=enc_alg, password=password) as writer:
                for chunk in iter_fractional_chunks(val, int(digits), int(base), int(chunk_size)):
                    writer.write(chunk.encode("ascii"))
                    written += len(chunk)
                    progress.progress(min(1.0, written / max(1, int(digits))))
            status.success(f"Saved to {out_path}")
        if verify:
            if fmt == "txt":
                fractional = read_fractional_digits_from_text(out_path, verify_samples)
            else:
                fractional = read_fractional_digits_from_chunked(out_path, verify_samples, password=password if encrypt else "")
            ok, kind = verify_fractional_digits(name, expr, base, verify_samples, fractional)
            if ok:
                st.success(f"Verification passed ({kind})")
            else:
                st.error(f"Verification failed ({kind})")
                return
        t1 = time.perf_counter()
        st.success(f"Done in {t1 - t0:.3f}s")
        st.metric("Digits", f"{int(digits):,}")
        st.metric("Theoretical bits", f"{_theoretical_bits(int(digits), int(base)):,}")
        st.code(_cli_command(name, expr, digits, base, engine, workers, fmt, binary_mode, compression, True, chunk_size, encrypt, encryption, add_label, verify, verify_samples, filename), language="bash")
        st.session_state.history.insert(0, f"{name} {digits} digits -> {out_path}")
        return

    method = "Fast" if engine == "mpmath-fast" else "Exact"
    s = render_in_base(val, int(digits), int(base), method)
    display = label_prefix + (base_prefix + s)
    meta = {"constant": name, "base": base, "digits": int(digits), "engine": engine}
    payload, mime = serialize_payload(display, fmt, meta, binary_mode=binary_mode)
    payload, suffix = apply_compression(payload, compression)
    encrypted = False
    if encrypt:
        if not password:
            st.error("Password is required for encryption.")
            return
        encrypted = True
        payload = encrypt_blob_v1(payload, password=password, algorithm=encryption, aad={"mime": mime, "format": fmt, "compression": compression})
        mime = "application/octet-stream"
    if verify:
        fractional = extract_fractional_digits(display)
        ok, kind = verify_fractional_digits(name, expr, base, verify_samples, fractional)
        if ok:
            st.success(f"Verification passed ({kind})")
        else:
            st.error(f"Verification failed ({kind})")
            return
    t1 = time.perf_counter()
    st.success(f"Done in {t1 - t0:.3f}s")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Digits", f"{int(digits):,}")
    with col2:
        st.metric("Size (bytes)", f"{len(payload):,}")
    with col3:
        st.metric("Bits", f"{len(payload) * 8:,}")
    with col4:
        st.metric("Theoretical bits", f"{_theoretical_bits(int(digits), int(base)):,}")
    st.code(display[:5000] + ("\n…" if len(display) > 5000 else ""), language="text")
    download_name = _final_name(filename, fmt, suffix, encrypted)
    st.download_button("Download", data=payload, file_name=download_name, mime=mime, use_container_width=True)
    savepath = st.text_input("Save to path", value=os.path.join(os.getcwd(), download_name))
    if st.button("Save locally", use_container_width=True):
        with open(savepath, "wb") as f:
            f.write(payload)
        st.toast(f"Saved to {savepath}")
    st.code(_cli_command(name, expr, digits, base, engine, workers, fmt, binary_mode, compression, False, chunk_size, encrypt, encryption, add_label, verify, verify_samples, filename), language="bash")
    st.session_state.history.insert(0, f"{name} {digits} digits -> {download_name}")


if __name__ == "__main__":
    main()
