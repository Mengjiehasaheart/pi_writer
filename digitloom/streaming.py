from typing import Iterable, Iterator

from mpmath import mp

from .constants import integer_to_base


def iter_fractional_digits(x, digits: int, base: int) -> Iterator[int]:
    f = x - mp.floor(x)
    for _ in range(int(digits)):
        f *= base
        d = int(mp.floor(f))
        yield d
        f -= d


def iter_fractional_chunks(x, digits: int, base: int, chunk_size: int) -> Iterator[str]:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    buf = []
    for d in iter_fractional_digits(x, digits, base):
        buf.append(alphabet[d])
        if len(buf) >= chunk_size:
            yield "".join(buf)
            buf = []
    if buf:
        yield "".join(buf)


def display_prefix(label_prefix: str, base_prefix: str, int_part: int, base: int) -> str:
    return f"{label_prefix}{base_prefix}{integer_to_base(int_part, base)}."


def iter_display_chunks(x, digits: int, base: int, chunk_size: int, label_prefix: str, base_prefix: str) -> Iterator[str]:
    int_part = int(mp.floor(x))
    yield display_prefix(label_prefix, base_prefix, int_part, base)
    for chunk in iter_fractional_chunks(x, digits, base, chunk_size):
        yield chunk


def iter_fractional_bytes(x, digits: int, base: int, chunk_size: int) -> Iterator[bytes]:
    for chunk in iter_fractional_chunks(x, digits, base, chunk_size):
        yield chunk.encode("ascii")


def collect_fractional_prefix(chunks: Iterable[bytes], count: int) -> bytes:
    out = bytearray()
    for chunk in chunks:
        need = int(count) - len(out)
        if need <= 0:
            break
        if len(chunk) <= need:
            out.extend(chunk)
        else:
            out.extend(chunk[:need])
            break
    return bytes(out)
