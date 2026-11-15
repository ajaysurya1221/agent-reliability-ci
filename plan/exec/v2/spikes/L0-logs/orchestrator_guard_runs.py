"""Runs-test guard and thinning against serial dependence. Three independent measures."""
import math, random, sys
from fractions import Fraction
from math import comb
sys.path.insert(0, "/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/L0-logs")
from rank_test import p_lower
A_REAL = Fraction(1, 120)
def series(rng, n, rho, sd):
    z = rng.gauss(0, 1); out = []
    for _ in range(n):
        out.append(z); z = rho * z + math.sqrt(1 - rho * rho) * rng.gauss(0, 1)
    return [int(math.exp(sd * v) * 10**9) for v in out]
def runs_p(x):
    s = sorted(x); n = len(s)
    med2 = s[n // 2] + s[(n - 1) // 2]
    signs = [1 if 2 * v > med2 else 0 for v in x if 2 * v != med2]
    n1 = sum(signs); n2 = len(signs) - n1
    if n1 == 0 or n2 == 0: return Fraction(1)
    r = 1 + sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    tot = comb(n1 + n2, n1); acc = 0
    for q in range(2, r + 1):
        k = q // 2
        if q % 2 == 0: acc += 2 * comb(n1 - 1, k - 1) * comb(n2 - 1, k - 1)
        else: acc += comb(n1 - 1, k) * comb(n2 - 1, k - 1) + comb(n1 - 1, k - 1) * comb(n2 - 1, k)
    return Fraction(acc, tot)
def run(n, m, rho, drop, sims, seed, thin, sd=0.45):
    rng = random.Random(seed); c = dict(none=0, runs05=0, runs10=0, runs20=0)
    for _ in range(sims):
        real = False; f05 = f10 = f20 = False
        for k in range(3):
            s = series(rng, n + m, rho, sd); x, y = s[:n], s[n:]
            if k == 0 and drop: y = [int(v * (1 - drop)) for v in y]
            rp = runs_p(x)
            f05 |= rp <= Fraction(1, 20); f10 |= rp <= Fraction(1, 10); f20 |= rp <= Fraction(1, 5)
            if thin > 1: x, y = x[::-1][::thin][::-1], y[::thin]
            if p_lower(x, y) <= A_REAL: real = True
        c["none"] += real; c["runs05"] += real and not f05; c["runs10"] += real and not f10; c["runs20"] += real and not f20
    return {k: round(v / sims, 3) for k, v in c.items()}
sims = int(sys.argv[1])
for thin in (1, 2, 3):
    print(f"--- every {thin} day(s); columns: no guard | runs guard at 0.05 | 0.10 | 0.20")
    for (m, n) in ((7, 21), (14, 42), (28, 84)):
        row = []
        for rho, drop in ((0, 0), (0.3, 0), (0.5, 0), (0.7, 0), (0, 0.45), (0.5, 0.45)):
            r = run(n, m, rho, drop, sims, 77 + n + int(rho * 10) + int(drop * 100) + thin, thin)
            row.append(f"rho{rho}/drop{drop}: {r['none']} {r['runs05']} {r['runs10']} {r['runs20']}")
        print(f"after {m} before {n}\n   " + "\n   ".join(row), flush=True)
