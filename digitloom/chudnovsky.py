from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from decimal import Decimal, getcontext


_A = 13591409
_B = 545140134
_C = 640320
_C3_OVER_24 = (_C**3) // 24


@dataclass(frozen=True)
class _BSTuple:
    p: int
    q: int
    t: int


def _bs(a: int, b: int) -> _BSTuple:
    if b - a == 1:
        if a == 0:
            return _BSTuple(1, 1, _A)
        k = a
        p = (6 * k - 5) * (2 * k - 1) * (6 * k - 1)
        q = k * k * k * _C3_OVER_24
        t = p * (_A + _B * k)
        if k & 1:
            t = -t
        return _BSTuple(p, q, t)
    m = (a + b) // 2
    left = _bs(a, m)
    right = _bs(m, b)
    return _BSTuple(
        left.p * right.p,
        left.q * right.q,
        left.t * right.q + left.p * right.t,
    )


def _combine(acc: _BSTuple, nxt: _BSTuple) -> _BSTuple:
    return _BSTuple(
        acc.p * nxt.p,
        acc.q * nxt.q,
        acc.t * nxt.q + acc.p * nxt.t,
    )


def _bs_range(ab):
    return _bs(ab[0], ab[1])


def chudnovsky_pi_decimal_string(digits_after_point: int, workers: int = 1) -> str:
    digits_after_point = int(digits_after_point)
    if digits_after_point < 0:
        raise ValueError("digits_after_point must be >= 0")
    workers = int(workers)
    if workers < 1:
        raise ValueError("workers must be >= 1")
    terms = int(digits_after_point / 14.181647462725477) + 2
    if workers == 1 or terms < 2000:
        bs = _bs(0, terms)
    else:
        chunk_count = min(workers, terms)
        bounds = [0]
        for i in range(1, chunk_count + 1):
            bounds.append((terms * i) // chunk_count)
        ranges = [(bounds[i], bounds[i + 1]) for i in range(chunk_count)]
        with ProcessPoolExecutor(max_workers=chunk_count) as ex:
            chunks = list(ex.map(_bs_range, ranges))
        bs = _BSTuple(1, 1, 0)
        for chunk in chunks:
            bs = _combine(bs, chunk)
    getcontext().prec = digits_after_point + 20
    q = Decimal(bs.q)
    t = Decimal(bs.t)
    pi = (Decimal(426880) * Decimal(10005).sqrt() * q) / t
    s = format(pi, "f")
    if "." not in s:
        s = s + "."
    head, tail = s.split(".", 1)
    if len(tail) < digits_after_point:
        tail = tail + ("0" * (digits_after_point - len(tail)))
    else:
        tail = tail[:digits_after_point]
    return head + "." + tail
