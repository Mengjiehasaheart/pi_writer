import math

from mpmath import mp


def constants_map():
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


def compute_precision(digits: int, base: int, guard: int = 30) -> int:
    return int(math.ceil(digits * math.log10(base))) + int(guard)


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
    s = sp.N(x, digits + 40)
    return mp.mpf(str(s))


def render_decimal_fast(x, digits: int) -> str:
    s = mp.nstr(x, digits + 30, min_fixed=-10**6, max_fixed=10**6)
    if "e" in s or "E" in s:
        return render_decimal_exact(x, digits)
    if "." not in s:
        return s + "." + ("0" * digits)
    a, b = s.split(".")
    if len(b) >= digits:
        return a + "." + b[:digits]
    return a + "." + b + ("0" * (digits - len(b)))


def integer_to_base(n: int, base: int) -> str:
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
    return "".join(reversed(s))


def fractional_digits(x, digits: int, base: int):
    f = x - mp.floor(x)
    out = []
    for _ in range(digits):
        f *= base
        d = int(mp.floor(f))
        out.append(d)
        f -= d
    return out


def digits_to_string(int_part: int, frac_digits, base: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    head = integer_to_base(int_part, base)
    tail = "".join(alphabet[d] for d in frac_digits)
    return head + ("." + tail if tail else "")


def render_decimal_exact(x, digits: int) -> str:
    int_part = int(mp.floor(x))
    tail = fractional_digits(x, digits, 10)
    return digits_to_string(int_part, tail, 10)


def render_in_base(x, digits: int, base: int, method: str) -> str:
    if base == 10 and method == "Fast":
        return render_decimal_fast(x, digits)
    int_part = int(mp.floor(x))
    tail = fractional_digits(x, digits, base)
    return digits_to_string(int_part, tail, base)


def pi_digits_spigot():
    q, r, t, k, n, l = 1, 0, 1, 1, 3, 3
    while True:
        if 4 * q + r - t < n * t:
            yield n
            q, r, t, k, n, l = (
                10 * q,
                10 * (r - n * t),
                t,
                k,
                ((10 * (3 * q + r)) // t) - 10 * n,
                l,
            )
        else:
            q, r, t, k, n, l = (
                q * k,
                (2 * q + r) * l,
                t * l,
                k + 1,
                (q * (7 * k + 2) + r * l) // (t * l),
                l + 2,
            )


def format_spigot_pi(prefix_digits: int) -> str:
    prefix_digits = int(prefix_digits)
    if prefix_digits < 1:
        raise ValueError("prefix_digits must be >= 1")
    g = pi_digits_spigot()
    first = next(g)
    out = [str(first), "."]
    for _ in range(prefix_digits - 1):
        out.append(str(next(g)))
    return "".join(out)
