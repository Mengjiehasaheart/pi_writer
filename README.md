# DigitLoom

DigitLoom is a minimal Streamlit app that generates high precision digits of mathematical constants like π, e, τ, √2, φ, γ, ζ(3), and more, 
then exports them to text, JSON, CSV, binary, or chunked artifacts to facilitate downstream research applications.

By: Mengjie Fan

## Main Content

- **Constants**: π, e, τ, √2, φ, Euler–Mascheroni γ, Apery’s ζ(3), Catalan’s G, ln 2, ζ(2), and custom expressions.
- **Bases**: Decimal (10) and Hexadecimal (16).
- **Exports**: `txt`, `json`, `csv`, `tsv`, `ndjson`, `bin` (ASCII digits or packed BCD), `sqlite`, `zip`, `dloom` (chunked).
- **Compression**: optional gzip.
- **Encryption**: optional AES‑256‑GCM or ChaCha20‑Poly1305 (password + scrypt).
- **Speed**: multi‑core π via Chudnovsky binary splitting.
- **Streaming**: chunked streaming to file plus infinite π stream (spigot).
- **Verification**: research‑grade digit checks (spigot/BBP or stability sampling).
- **Random access**: π hex digit extraction (BBP).
- **Sizing intel**: Instant byte and bit counts plus theoretical information content in bits.

## Run

- UI: `python3 -m digitloom start` (or `./run.sh`)
- CLI generate: `python3 -m digitloom generate --help`
- CLI stream π: `python3 -m digitloom stream-pi --infinite --out pi.txt`
- Chunked output: `python3 -m digitloom generate --format dloom --stream --chunk-size 10000 --out digits`
- Unpack chunked: `python3 -m digitloom unpack digits.dloom`
- π hex extraction: `python3 -m digitloom pi-hex --start 0 --count 64`
- Verify during generation: `python3 -m digitloom generate --verify --verify-samples 2000 --out digits`

## Chunked container (dloom)

`dloom` stores fractional digits in hashed chunks with metadata in the header. Chunks can be compressed and encrypted independently, enabling large, streamable artifacts without loading full payloads in memory.

## Canonical definitions

π via geometry and series; a classic fast series is Chudnovsky’s formula:

$$
\frac{1}{\pi} = \frac{12}{640320^{3/2}} \sum_{k=0}^{\infty} \frac{(-1)^k\,(6k)!\,(13591409+545140134k)}{(3k)!\,(k!)^3\,(640320)^{3k}}
$$

e by the exponential series:

$$
 e = \sum_{n=0}^{\infty} \frac{1}{n!}
$$

ζ(2) and τ:

$$
\zeta(2)=\frac{\pi^2}{6},\qquad \tau=2\pi
$$

φ and √2:

$$
\varphi=\frac{1+\sqrt{5}}{2},\qquad \sqrt{2}
$$

## Exact digits in base b

For a real number x and integer base b≥2, DigitLoom computes the fractional digits by repeated multiplication:

$$
\text{Let } x = \lfloor x \rfloor + f,\quad d_k = \lfloor b f_{k-1} \rfloor,\quad f_k = b f_{k-1} - d_k
$$

The fractional expansion is \(0.\,d_1d_2\dots d_N\) in base b. This is precise given sufficient working precision.

## Information content and file size

- Theoretical information bits for N base‑b digits:

$$
I \approx N\,\log_2 b
$$

- Practical file sizes depend on format:
  - Plain text UTF‑8: ~1 byte per character
  - JSON/CSV: text digits plus structural overhead
  - Binary (packed BCD): 1 digit = 4 bits; two digits per byte
