import re
from typing import Tuple

from mpmath import mp

from .bbp import pi_hex_digits
from .chunked import ChunkedReader
from .constants import compute_precision, constants_map, pi_digits_spigot, safe_custom
from .streaming import collect_fractional_prefix, iter_fractional_bytes


def extract_fractional_digits(display: str) -> str:
    if "." not in display:
        return ""
    return display.split(".", 1)[1]


def _pi_spigot_prefix(count: int) -> str:
    g = pi_digits_spigot()
    next(g)
    out = []
    for _ in range(int(count)):
        out.append(str(next(g)))
    return "".join(out)


def _mp_prefix(constant_name: str, expr: str, base: int, samples: int) -> str:
    p = compute_precision(samples, base, guard=60)
    mp.dps = p
    c = constants_map()
    if constant_name == "Custom":
        val = safe_custom(expr, p)
    else:
        val = c[constant_name]()
    chunk_size = min(1024, max(1, int(samples)))
    data = collect_fractional_prefix(iter_fractional_bytes(val, samples, base, chunk_size), samples)
    return data.decode("ascii")


def verify_fractional_digits(constant_name: str, expr: str, base: int, samples: int, fractional_digits: str) -> Tuple[bool, str]:
    samples = int(samples)
    if samples <= 0:
        return True, "verification skipped"
    if constant_name == "Pi (π)" and int(base) == 10:
        expected = _pi_spigot_prefix(min(samples, len(fractional_digits)))
        actual = fractional_digits[: len(expected)]
        ok = expected == actual
        return ok, "pi spigot"
    if constant_name == "Pi (π)" and int(base) == 16:
        count = min(samples, len(fractional_digits))
        expected = pi_hex_digits(0, count)
        actual = fractional_digits[:count].upper()
        ok = expected == actual
        return ok, "pi bbp"
    expected = _mp_prefix(constant_name, expr, int(base), min(samples, len(fractional_digits)))
    actual = fractional_digits[: len(expected)]
    ok = expected == actual
    return ok, "mp stability"


def read_fractional_digits_from_text(path: str, samples: int) -> str:
    samples = int(samples)
    if samples <= 0:
        return ""
    seen_dot = False
    out = []
    with open(path, "rb") as f:
        while len(out) < samples:
            chunk = f.read(8192)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="ignore")
            for ch in text:
                if not seen_dot:
                    if ch == ".":
                        seen_dot = True
                    continue
                if re.match(r"[0-9a-fA-F]", ch):
                    out.append(ch)
                    if len(out) >= samples:
                        break
    return "".join(out)


def read_fractional_digits_from_chunked(path: str, samples: int, password: str = "") -> str:
    samples = int(samples)
    if samples <= 0:
        return ""
    out = bytearray()
    with ChunkedReader(path, password=password) as reader:
        for chunk in reader:
            need = samples - len(out)
            if need <= 0:
                break
            if len(chunk) <= need:
                out.extend(chunk)
            else:
                out.extend(chunk[:need])
                break
    return out.decode("ascii")
