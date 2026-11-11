# Balanced rounds: conditional error control

1. **ASSUMED.** Freeze a finite grid of N cells, delta=1/10, alpha=1/20,
   stakes q in {1/4,1/2}, and equal mixture weights before outcomes. In round r,
   cell c produces d[r,c] in {-1,0,1}. Cell laws are fixed across rounds and
   differences are jointly independent across distinct (round,cell) pairs.
   The theorem conditions on the manifest, including its cell order.
2. **PROVED-IN-LINE.** If paired Bernoulli outcomes are (A,B), d=B-A and
   E[d]=P(B=1)-P(A=1)=Delta_c by linearity. No independence between A and B
   is required. Arbitrary feasible within-pair coupling is allowed. This does
   not license shared random outcomes across cells or rounds.
3. **PROVED-IN-LINE.** Set lambda_q=q/(1-delta) for PASS and mu_q=q/(1+delta)
   for BLOCK. Since d+delta lies in [-(1-delta),1+delta], both
   1+lambda_q(d+delta) and 1-mu_q(d+delta) are at least 1-q>=0.
   Consequently their expectations are nonnegative too. For the selected q
   they are strictly positive. Stakes are constant across cells within a
   component; cell-dependent stakes would invalidate the following AM-GM step.
4. **PROVED-IN-LINE.** Let F[r-1] contain all previous complete rounds.
   Independence within the round and from F[r-1] gives
   E[B_q[r] | F[r-1]] = product_c (1+lambda_q(Delta_c+delta))
   for B_q[r]=product_c(1+lambda_q(d[r,c]+delta)). Without independence,
   expectation of the product need not factor.
5. **PROVED-IN-LINE.** Write Delta=(sum_c Delta_c)/N. AM-GM for the N
   nonnegative expectation factors bounds this product by
   (1+lambda_q(Delta+delta))^N. If Delta<=-delta, the base lies in [0,1],
   so E[B_q[r]|F[r-1]]<=1. Its nonnegativity follows either from its being
   an average of nonnegative factors, or from Delta>=-1 and lambda_q<=1/(1-delta).
6. **PROVED-IN-LINE.** For BLOCK replace lambda_q by -mu_q. The same argument
   gives E[C_q[r]|F[r-1]]<= (1-mu_q(Delta+delta))^N<=1 whenever Delta>=-delta.
   The base is nonnegative because Delta<=1 and mu_q<=1/(1+delta).
7. **PROVED-IN-LINE.** W_q[0]=1 and W_q[r]=W_q[r-1]B_q[r] form a
   nonnegative supermartingale at round ends under the PASS null. The fixed
   average of the two W_q processes also does, by linearity of conditional
   expectation. The BLOCK mixture has the analogous property under its null.
   This is an average of full products, not a product of per-cell averages.
8. **PROVED-IN-LINE.** Ville's inequality gives
   P(sup_r W_PASS[r]>=2/alpha | manifest)<=alpha/2=1/40, and similarly for
   BLOCK under its null. Stopping at either crossing can only reduce the
   corresponding crossing event. At Delta=-delta both directional bounds
   apply; their union is at most alpha=1/20. These are frequentist outcome
   probabilities, not posterior probabilities of hypotheses.
9. **PROVED-IN-LINE.** Equality in AM-GM for these strictly positive factors
   and q>0 requires all Delta_c equal. At Delta_c=-delta for every cell,
   each expected round factor is exactly 1; the processes are martingales.
   This does not imply equality in Ville's bound for the finite horizon.
   q=0 would also yield equality everywhere; it is not a selected stake.
10. **PROVED-IN-LINE.** Stationarity plus joint independence is sufficient;
    weaker conditional assumptions would also suffice if each next round's
    independent conditional means obey the null. This spike does not establish
    those assumptions for a real provider. Mere pairwise independence is not
    sufficient to factor an arbitrary product.

## Why mid-round looks fail

11. **PROVED-IN-LINE.** Take N=20, a fixed order of nine deterministic +1
    cells followed by eleven deterministic -1 cells. The suite mean is
    (9-11)/20=-1/10. Deterministic variables satisfy all independence and
    stationarity assumptions. After the first nine pairs the PASS mixture is
    ((47/36)^9+(29/18)^9)/2 >= 40. For eight pairs it is below 40.
    Thus allowing a look after every pair yields false PASS probability
    exactly 1, exceeding 1/40. At complete rounds, each PASS component is
    multiplied by (1+11q/9)^9(1-q)^11<1, so PASS never occurs.
    BLOCK round products are also strictly less than 1 by strict AM-GM.
    Balanced inference remains INCONCLUSIVE for every complete-round horizon.
12. **CHECKED-BY-ENUMERATION.** Tests and Table E compare the rational stream
    procedure and the absorbing DP: pairwise looks PASS at pair 9 with mass 1;
    twenty complete rounds remain INCONCLUSIVE with mass 1. A terminal partial
    round ending at pair 9 is the same failure. Ending execution midway without
    evaluating a new statistical look does not itself create a false PASS;
    it simply provides no new protected decision.

## Exact computation

13. **PROVED-IN-LINE.** A cell's count polynomial is
    p_minus*x+p_zero+p_plus*y. Multiplying these polynomials yields the joint
    distribution of the round's minus/plus count increments. Convolving the
    surviving state distribution with all N factors before absorption is
    algebraically identical to convolution with the full round polynomial.
    Counts suffice because stakes are fixed and multiplication commutes.
14. **PROVED-IN-LINE.** Integer weights and a common denominator retain all
    probability mass. For general trinomials, plus-count polynomial coefficients
    are packed into base 2^w digits, where 2^w-1 exceeds the final denominator.
    Every intermediate coefficient and their total are smaller than this base;
    additions/multiplications by integer cell weights introduce no carries.
    Masks split the exact PASS/BLOCK count regions. Binary folding adds the
    upper half of the digits onto the lower half repeatedly. Each coefficient
    remains a sum of disjoint original coefficients, so no carry is possible.
    The final digit equals their exact sum (equivalently, reduction modulo
    2^w-1, since that sum is below the modulus). Expected pairs sums
    survival probability before each scheduled pair, counting complete rounds.
15. **CHECKED-BY-ENUMERATION.** Exhaustive ordered paths with rational weights,
    including both competing absorbing decisions, check probabilities and cost.
    Independent S1 enumeration checks both binary reductions. No floating-point
    number determines a crossing, probability comparison, or search winner.
