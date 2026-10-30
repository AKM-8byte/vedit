"""Easing fonksiyonları. Hepsi 0..1 → 0..1 (back/elastic hafif taşabilir)."""
from __future__ import annotations

import math


def linear(t):
    return t


def ease_in(t):
    return t * t


def ease_out(t):
    return 1 - (1 - t) * (1 - t)


def ease_in_out(t):
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def in_cubic(t):
    return t ** 3


def out_cubic(t):
    return 1 - (1 - t) ** 3


def in_out_cubic(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def in_sine(t):
    return 1 - math.cos(t * math.pi / 2)


def out_sine(t):
    return math.sin(t * math.pi / 2)


def in_out_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2


def in_expo(t):
    return 0 if t == 0 else 2 ** (10 * t - 10)


def out_expo(t):
    return 1 if t == 1 else 1 - 2 ** (-10 * t)


def in_out_expo(t):
    if t in (0, 1):
        return t
    return 2 ** (20 * t - 10) / 2 if t < 0.5 else (2 - 2 ** (-20 * t + 10)) / 2


_C1 = 1.70158
_C3 = _C1 + 1


def in_back(t):
    return _C3 * t ** 3 - _C1 * t ** 2


def out_back(t):
    return 1 + _C3 * (t - 1) ** 3 + _C1 * (t - 1) ** 2


def in_out_back(t):
    c2 = _C1 * 1.525
    if t < 0.5:
        return ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2
    return ((2 * t - 2) ** 2 * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2


def out_elastic(t):
    if t in (0, 1):
        return t
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


def in_elastic(t):
    if t in (0, 1):
        return t
    return -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * (2 * math.pi) / 3)


def out_bounce(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def in_bounce(t):
    return 1 - out_bounce(1 - t)


def hold(t):
    return 0.0 if t < 1 else 1.0


def cubic_bezier(x1, y1, x2, y2):
    """CSS cubic-bezier eşdeğeri."""

    def bez(t, a, b):
        return 3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3

    def f(x):
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if bez(mid, x1, x2) < x:
                lo = mid
            else:
                hi = mid
        return bez((lo + hi) / 2, y1, y2)

    return f


EASINGS = {
    "linear": linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "in_cubic": in_cubic,
    "out_cubic": out_cubic,
    "in_out_cubic": in_out_cubic,
    "in_sine": in_sine,
    "out_sine": out_sine,
    "in_out_sine": in_out_sine,
    "in_expo": in_expo,
    "out_expo": out_expo,
    "in_out_expo": in_out_expo,
    "in_back": in_back,
    "out_back": out_back,
    "in_out_back": in_out_back,
    "in_elastic": in_elastic,
    "out_elastic": out_elastic,
    "in_bounce": in_bounce,
    "out_bounce": out_bounce,
    "hold": hold,
}


def get(name) -> callable:
    """İsim ya da [x1,y1,x2,y2] bezier listesi kabul eder."""
    if callable(name):
        return name
    if isinstance(name, (list, tuple)) and len(name) == 4:
        return cubic_bezier(*map(float, name))
    return EASINGS.get(str(name or "linear"), linear)


def apply(name, t: float) -> float:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return get(name)(t)
