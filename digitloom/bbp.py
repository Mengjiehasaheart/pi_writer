import math

from mpmath import mp


def _prec_bits(n: int) -> int:
    n = int(n)
    if n < 1:
        return 128
    return max(128, int(math.log2(n + 1)) + 128)


def _series(j: int, n: int, prec: int):
    mp.prec = prec
    s = mp.mpf(0)
    for k in range(n + 1):
        r = 8 * k + j
        s += mp.mpf(pow(16, n - k, r)) / r
        s = s - mp.floor(s)
    t = mp.mpf(0)
    k = n + 1
    pow16 = mp.mpf(1) / 16
    eps = mp.power(2, -prec + 16)
    while True:
        r = 8 * k + j
        term = pow16 / r
        if term < eps:
            break
        t += term
        k += 1
        pow16 /= 16
    return (s + t) % 1


def pi_hex_digit(n: int) -> int:
    n = int(n)
    if n < 0:
        raise ValueError("n must be >= 0")
    prec = _prec_bits(n)
    s1 = _series(1, n, prec)
    s4 = _series(4, n, prec)
    s5 = _series(5, n, prec)
    s6 = _series(6, n, prec)
    x = (4 * s1 - 2 * s4 - s5 - s6) % 1
    return int(mp.floor(16 * x))


def pi_hex_digits(start: int, count: int) -> str:
    start = int(start)
    count = int(count)
    if start < 0:
        raise ValueError("start must be >= 0")
    if count < 0:
        raise ValueError("count must be >= 0")
    alphabet = "0123456789ABCDEF"
    return "".join(alphabet[pi_hex_digit(start + i)] for i in range(count))
