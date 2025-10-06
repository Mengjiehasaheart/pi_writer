# DigitLoom

DigitLoom is a minimal, elegant Streamlit app that generates high‑precision digits of mathematical constants like π, e, τ, √2, φ, γ, ζ(3), and more, then exports them to text, JSON, CSV, or binary.

By: Mengjie Fan

## Highlights

- **Constants**: π, e, τ, √2, φ, Euler–Mascheroni γ, Apery’s ζ(3), Catalan’s G, ln 2, ζ(2), and custom expressions.
- **Bases**: Decimal (10) and Hexadecimal (16).
- **Exports**: `txt`, `json`, `csv`, `bin` (ASCII digits or packed BCD).
- **Sizing intel**: Instant byte and bit counts plus theoretical information content in bits.


### Canonical definitions

- π via geometry and series; a classic fast series is Chudnovsky’s formula:
  $$
  \frac{1}{\pi} = \frac{12}{640320^{3/2}} \sum_{k=0}^{\infty} \frac{(-1)^k\,(6k)!\,(13591409+545140134k)}{(3k)!\,(k!)^3\,(640320)^{3k}}
  $$
- e by the exponential series:
  $$
  e = \sum_{n=0}^{\infty} \frac{1}{n!}
  $$
- ζ(2) and τ:
  $$
  \zeta(2)=\frac{\pi^2}{6},\qquad \tau=2\pi
  $$
- φ and √2:
  $$
  \varphi=\frac{1+\sqrt{5}}{2},\qquad \sqrt{2}
  $$

### Exact digits in base b

For a real number x and integer base b≥2, DigitLoom computes the fractional digits by repeated multiplication:
$$
\text{Let } x = \lfloor x \rfloor + f,\quad d_k = \lfloor b f_{k-1} \rfloor,\quad f_k = b f_{k-1} - d_k
$$
The fractional expansion is $0.\,d_1d_2\dots d_N$ in base b. This is precise given sufficient working precision.

### Information content and file size

- Theoretical information bits for N base‑b digits:
  $$
  I \approx N\,\log_2 b
  $$
- Practical file sizes depend on format:
  - Plain text UTF‑8: ~1 byte per character
  - JSON/CSV: text digits plus structural overhead
  - Binary (packed BCD): 1 digit = 4 bits; two digits per byte
