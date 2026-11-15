"""Compare guards against serial dependence. Three independent measures, AR(1) in log space."""
import math, random, sys, time
from fractions import Fraction
sys.path.insert(0, "/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/L0-logs")
from rank_test import p_lower
A_REAL = Fraction(1, 120); A_40 = Fraction(1, 40)
def series(rng, n, rho, sd):
    z = rng.gauss(0, 1); out = []
    for _ in range(n):
        out.append(z); z = rho * z + math.sqrt(1 - rho * rho) * rng.gauss(0, 1)
    return [int(math.exp(sd * v) * 10**9) for v in out]
def run(n, m, rho, drop, sims, seed, sd=0.45):
    rng = random.Random(seed); c = dict(g0=0, g1=0, g2=0, g3=0, g4=0)
    for _ in range(sims):
        real = False; half = False; roll120 = False; roll40 = False; beat = False
        for k in range(3):
            s = series(rng, n + m, rho, sd); x, y = s[:n], s[n:]
            if k == 0 and drop: y = [int(v * (1 - drop)) for v in y]
            p = p_lower(x, y)
            h = (n + 1) // 2
            if p_lower(x[:h], x[h:]) <= A_REAL: half = True
            pl = [p_lower(x[: t - m], x[t - m : t]) for t in range(2 * m, n + 1)]
            if pl and min(pl) <= A_REAL: roll120 = True
            if pl and min(pl) <= A_40: roll40 = True
            if p <= A_REAL:
                real = True
                if not pl or p < min(pl): beat = True
        c["g0"] += real; c["g1"] += real and not half; c["g2"] += real and not roll120
        c["g4"] += real and not roll40; c["g3"] += beat
    return {k: round(v / sims, 4) for k, v in c.items()}
sims = int(sys.argv[1])
print("g0 none | g1 half-split | g2 rolling<=1/120 | g4 rolling<=1/40 | g3 must beat every placebo")
for (m, n) in ((7, 21), (14, 42), (28, 84)):
    for rho, drop in ((0, 0), (0.3, 0), (0.5, 0), (0.7, 0), (0, 0.45), (0, 0.33), (0.5, 0.45)):
        t = time.time(); r = run(n, m, rho, drop, sims, 1000 + n + int(rho * 10) + int(drop * 100))
        print(f"after {m:2d} before {n:2d} rho {rho} drop {drop}: {r}  ({time.time()-t:.0f}s)", flush=True)
