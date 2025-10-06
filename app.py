import os
import io
import json
import math
import time
from typing import Tuple
import streamlit as st
from mpmath import mp

st.set_page_config(page_title="DigitLoom", page_icon="🧮", layout="wide")

def style():
    st.markdown(
        """
        <style>
        :root {--brand:#0ea5e9;--ink:#0b132b;--muted:#6b7280;--bg0:#0b132b;--bg1:#16213e;--bg2:#1f2937;--fg:#e5e7eb}
        .stApp {background: radial-gradient(60% 80% at 20% 10%, rgba(14,165,233,.15), transparent 40%), radial-gradient(60% 80% at 100% 0%, rgba(99,102,241,.15), transparent 40%), linear-gradient(180deg, var(--bg0), var(--bg1))}
        .title-wrap {padding: 24px 20px 10px; border-bottom: 1px solid rgba(255,255,255,.08); margin-bottom: 12px}
        .title {font-weight: 800; font-size: 28px; letter-spacing: .2px; color: white}
        .subtitle {color: var(--fg); opacity:.8; margin-top: 6px}
        .chip {display:inline-block; padding:6px 10px; border-radius:20px; background:rgba(14,165,233,.15); color:#7dd3fc; font-size:12px; margin-left:8px}
        .metric {background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02)); padding:14px 16px; border-radius:12px; border:1px solid rgba(255,255,255,.08)}
        .codebox {background: #0a0f1f; border:1px solid rgba(255,255,255,.08);}
        </style>
        """,
        unsafe_allow_html=True,
    )

def constants():
    return {
        "Pi (π)": lambda: mp.pi,
        "Tau (τ)": lambda: mp.tau,
        "Euler's e": lambda: mp.e,
        "Sqrt(2)": lambda: mp.sqrt(2),
        "Golden ratio (φ)": lambda: (1 + mp.sqrt(5)) / 2,
        "Euler–Mascheroni (γ)": lambda: mp.euler,
        "Apery's ζ(3)": lambda: mp.zeta(3),
        "Catalan (G)": lambda: mp.catalan,
        "ln 2": lambda: mp.log(2),
        "ζ(2) = π²/6": lambda: mp.zeta(2),
        "Custom": None,
    }

def safe_custom(expr: str, digits: int):
    import sympy as sp
    allowed = {
        "pi": sp.pi,
        "E": sp.E,
        "EulerGamma": sp.EulerGamma,
        "Catalan": sp.Catalan,
        "GoldenRatio": sp.GoldenRatio,
        "zeta": sp.zeta,
        "sqrt": sp.sqrt,
        "log": sp.log,
        "ln": sp.log,
        "exp": sp.exp,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,
        "sinh": sp.sinh,
        "cosh": sp.cosh,
        "tanh": sp.tanh,
        "gamma": sp.gamma,
    }
    x = sp.sympify(expr, locals=allowed)
    s = sp.N(x, digits + 20)
    return mp.mpf(str(s))

def compute_precision(digits: int, base: int):
    return int(math.ceil(digits * math.log10(base))) + 20

def integer_to_base(n: int, base: int):
    if base == 10:
        return str(n)
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    s = []
    m = abs(n)
    while m:
        m, r = divmod(m, base)
        s.append(alphabet[r])
    if n < 0:
        s.append("-")
    return ("".join(reversed(s)))

def fractional_digits(x, digits: int, base: int):
    f = x - mp.floor(x)
    out = []
    for _ in range(digits):
        f *= base
        d = int(mp.floor(f))
        out.append(d)
        f -= d
    return out

def digits_to_string(int_part: int, frac_digits, base: int):
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    head = integer_to_base(int_part, base)
    tail = "".join(alphabet[d] for d in frac_digits)
    return head + ("." + tail if len(tail) else "")

def render_decimal_fast(x, digits: int):
    s = mp.nstr(x, digits + 25, min_fixed=-10**6, max_fixed=10**6)
    if "e" in s or "E" in s:
        return render_decimal_exact(x, digits)
    if "." not in s:
        return s + "." + ("0" * digits)
    a, b = s.split(".")
    if len(b) >= digits:
        return a + "." + b[:digits]
    return a + "." + b + ("0" * (digits - len(b)))

def render_decimal_exact(x, digits: int):
    p = compute_precision(digits, 10)
    mp.dps = p
    int_part = int(mp.floor(x))
    tail = fractional_digits(x, digits, 10)
    return digits_to_string(int_part, tail, 10)

def render_in_base(x, digits: int, base: int, method: str):
    if base == 10 and method == "Fast":
        return render_decimal_fast(x, digits)
    int_part = int(mp.floor(x))
    tail = fractional_digits(x, digits, base)
    return digits_to_string(int_part, tail, base)

def make_bytes(s: str, fmt: str, meta: dict, binary_mode: str):
    if fmt == "txt":
        return s.encode("utf-8"), "text/plain"
    if fmt == "json":
        payload = dict(meta)
        payload["value"] = s
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json"
    if fmt == "csv":
        header = ["constant", "base", "digits", "value"]
        row = [meta.get("constant"), meta.get("base"), str(meta.get("digits")), s]
        csv = ",".join(header) + "\n" + ",".join(row) + "\n"
        return csv.encode("utf-8"), "text/csv"
    if fmt == "bin":
        if binary_mode == "ASCII digits":
            return s.encode("ascii", errors="ignore"), "application/octet-stream"
        raw = []
        for ch in s:
            if ch == ".":
                continue
            d = ord(ch)
            if 48 <= d <= 57:
                raw.append(d - 48)
            elif 97 <= d <= 122:
                raw.append(d - 87)
            elif 65 <= d <= 90:
                raw.append(d - 55)
        out = bytearray()
        i = 0
        while i < len(raw):
            hi = raw[i]
            lo = raw[i + 1] if i + 1 < len(raw) else 0
            out.append(((hi & 0x0F) << 4) | (lo & 0x0F))
            i += 2
        return bytes(out), "application/octet-stream"
    return s.encode("utf-8"), "text/plain"

def estimate_bits(bytes_len: int):
    return bytes_len * 8

def theoretical_bits(digits: int, base: int):
    return int(digits * math.log2(base))

def ui_header():
    st.markdown(
        """
        <div class="title-wrap">
          <div class="title">DigitLoom<span class="chip">by Mengjie Fan</span></div>
          <div class="subtitle">digits into clean files sized for whatever your needs.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def main():
    style()
    ui_header()
    c = constants()
    with st.sidebar:
        st.markdown("Mode")
        colA, colB = st.columns(2)
        with colA:
            base = st.selectbox("Base", options=[10, 16], index=0)
        with colB:
            method = st.selectbox("Algorithm", options=["Fast", "Exact"], index=0, help="Fast for base 10, Exact for any base")
        name = st.selectbox("Constant", options=list(c.keys()), index=0)
        expr = ""
        if name == "Custom":
            expr = st.text_input("Expression", value="sin(1)+cos(1)+pi/7", help="Use pi, E, EulerGamma, Catalan, GoldenRatio, zeta, sqrt, log, exp, sin, cos, ...")
        digits = st.number_input("Digits after point", min_value=1, max_value=2_000_000, value=1000, step=1000)
        fmt = st.selectbox("File format", options=["txt", "json", "csv", "bin"], index=0)
        binary_mode = "ASCII digits"
        if fmt == "bin":
            binary_mode = st.selectbox("Binary encoding", options=["ASCII digits", "Packed BCD"], index=0)
        add_label = st.checkbox("Include label prefix", value=True)
        filename = st.text_input("Filename (no extension)", value="digits")
        generate = st.button("Generate", type="primary", use_container_width=True)

    if generate:
        t0 = time.perf_counter()
        p = compute_precision(digits, base)
        mp.dps = p
        if name == "Custom":
            val = safe_custom(expr, p)
        else:
            val = c[name]()
        s = render_in_base(val, digits, base, method)
        label = name.split(" ")[0]
        label_map = {10: "", 16: "0x"}
        display = (label + " = " + (label_map[base] + s)) if add_label else (label_map[base] + s)
        meta = {"constant": name, "base": base, "digits": digits, "author": "Mengjie Fan"}
        b, mime = make_bytes(display, fmt, meta, binary_mode)
        t1 = time.perf_counter()

        st.success("Done")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Digits", f"{digits:,}")
        with col2:
            st.metric("Size (bytes)", f"{len(b):,}")
        with col3:
            st.metric("Bits", f"{estimate_bits(len(b)):,}")
        with col4:
            st.metric("Theoretical bits", f"{theoretical_bits(digits, base):,}")

        st.code(display[:5000] + ("\n…" if len(display) > 5000 else ""), language="text")
        colD, colE = st.columns([1,1])
        with colD:
            st.download_button("Download", data=b, file_name=f"{filename}.{fmt}", mime=mime, use_container_width=True)
        with colE:
            savepath = st.text_input("Save to path", value=os.path.join(os.getcwd(), f"{filename}.{fmt}"))
            if st.button("Save locally", use_container_width=True):
                with open(savepath, "wb") as f:
                    f.write(b)
                st.toast(f"Saved to {savepath}")
        st.caption(f"Computed in {t1 - t0:.3f}s at precision {p} dps")

if __name__ == "__main__":
    main()

