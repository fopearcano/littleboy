"""Deterministic, stdlib-only statistics for calibrated CV inference.

Cross-validated fold gains are *not* independent (every fold shares most of its
training data with every other), so a naive t-test over fold gains is overconfident.
The standard remedy is the **Nadeau-Bengio corrected resampled t-test**, whose
variance correction ``(1/m + n_test/n_train)`` keeps the test honest no matter how
many times CV is repeated. Its p-value needs the Student-t CDF, implemented here
from the regularised incomplete beta function (continued fraction; no scipy).

The **exact sign test** is the assumption-light companion: on paired out-of-fold
predictions, count the cases only the fitted policy got right (``b``) and only the
built-in got right (``c``); under "no difference" the discordant cases are fair
coin flips, so the p-value is an exact binomial tail. Everything here is a pure
function of its inputs -- deterministic, testable against closed forms.
"""

from __future__ import annotations

import math

_BETACF_MAX_ITER = 300
_BETACF_EPS = 3e-15
_BETACF_FPMIN = 1e-300


def _betacf(a: float, b: float, x: float) -> float:
    """Continued-fraction kernel for the incomplete beta (Lentz's method)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _BETACF_FPMIN:
        d = _BETACF_FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, _BETACF_MAX_ITER + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _BETACF_FPMIN:
            d = _BETACF_FPMIN
        c = 1.0 + aa / c
        if abs(c) < _BETACF_FPMIN:
            c = _BETACF_FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _BETACF_FPMIN:
            d = _BETACF_FPMIN
        c = 1.0 + aa / c
        if abs(c) < _BETACF_FPMIN:
            c = _BETACF_FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _BETACF_EPS:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """``I_x(a, b)``, the regularised incomplete beta function, for a, b > 0."""
    if a <= 0.0 or b <= 0.0:
        raise ValueError("a and b must be positive")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, df: float) -> float:
    """The CDF of Student's t-distribution with ``df`` degrees of freedom."""
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    if t == 0.0:
        return 0.5
    x = df / (df + t * t)
    tail = 0.5 * regularized_incomplete_beta(df / 2.0, 0.5, x)
    return 1.0 - tail if t > 0 else tail


def student_t_two_sided_p(t: float, df: float) -> float:
    """Two-sided p-value for a t-statistic."""
    return min(1.0, 2.0 * (1.0 - student_t_cdf(abs(t), df)))


def student_t_critical(df: float, alpha: float = 0.05) -> float:
    """The two-sided critical value ``t*`` with ``P(|T| > t*) = alpha`` (by bisection)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    target = 1.0 - alpha / 2.0
    lo, hi = 0.0, 1.0
    while student_t_cdf(hi, df) < target:
        hi *= 2.0
        if hi > 1e9:  # pragma: no cover - unreachable for sane alpha/df
            break
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if student_t_cdf(mid, df) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def sign_test_p(b: int, c: int) -> float:
    """Exact two-sided sign-test p-value over ``b + c`` discordant pairs.

    Under the null (the two classifiers are equally good), each discordant pair
    favours either side with probability 1/2, so the p-value is an exact binomial
    tail: ``2 * P(X <= min(b, c))`` for ``X ~ Binomial(b + c, 1/2)``, capped at 1.
    ``b + c == 0`` (no disagreements at all) gives 1.0.
    """
    if b < 0 or c < 0:
        raise ValueError("counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    m = min(b, c)
    tail = sum(math.comb(n, i) for i in range(m + 1)) / 2.0**n
    return min(1.0, 2.0 * tail)
