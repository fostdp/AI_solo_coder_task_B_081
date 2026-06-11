import math
import random
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


class RestrictedCubicSpline:

    def __init__(self, knots: Optional[List[float]] = None, nk: int = 4):
        self.knots = knots
        self.nk = nk
        self.coefficients: Optional[List[float]] = None
        self.r_squared = 0.0

    def _place_knots(self, x_values: List[float]) -> List[float]:
        if self.knots:
            return sorted(self.knots)
        xs = sorted(set(x_values))
        if len(xs) < self.nk:
            return xs
        percentiles = [i / (self.nk - 1) for i in range(self.nk)]
        knots = []
        for p in percentiles:
            idx = min(int(p * (len(xs) - 1)), len(xs) - 1)
            knots.append(xs[idx])
        return sorted(set(knots))

    @staticmethod
    def _spline_basis(x: float, knots: List[float], k: int) -> float:
        if k >= len(knots) - 1:
            return 0.0
        tk = knots[k]
        tk1 = knots[-2]
        tk2 = knots[-1]
        def h(z, t):
            return max(0.0, (z - t) ** 3) if z > t else 0.0
        left = (h(x, tk) - h(x, tk2)) / (tk2 - tk) if tk2 != tk else 0.0
        right = (h(x, tk1) - h(x, tk2)) / (tk2 - tk1) if tk2 != tk1 else 0.0
        return left - right

    def design_matrix(self, x_values: List[float]) -> List[List[float]]:
        knots = self._place_knots(x_values)
        self.knots = knots
        X = []
        for x in x_values:
            row = [1.0, x]
            for k in range(len(knots) - 2):
                row.append(self._spline_basis(x, knots, k))
            X.append(row)
        return X

    def fit(self, x_values: List[float], y_values: List[float],
            weights: Optional[List[float]] = None) -> List[float]:
        X = self.design_matrix(x_values)
        n = len(X)
        p = len(X[0]) if X else 0
        if weights is None:
            weights = [1.0] * n
        XtW = [[X[i][j] * weights[i] for j in range(p)] for i in range(n)]
        XtWX = [[sum(XtW[k][i] * X[k][j] for k in range(n))
                 for j in range(p)] for i in range(p)]
        XtWy = [sum(XtW[k][i] * y_values[k] for k in range(n))
                for i in range(p)]
        try:
            self.coefficients = self._solve(XtWX, XtWy)
        except Exception:
            self.coefficients = [sum(y_values) / max(n, 1)] + [0.0] * (p - 1)
        pred = [self.predict(x) for x in x_values]
        y_mean = sum(y_values) / n
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        ss_res = sum((y_values[i] - pred[i]) ** 2 for i in range(n))
        self.r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return self.coefficients

    @staticmethod
    def _solve(A: List[List[float]], b: List[float]) -> List[float]:
        n = len(A)
        M = [row[:] + [b[i]] for i, row in enumerate(A)]
        for col in range(n):
            piv = max(range(col, n), key=lambda r: abs(M[r][col]))
            M[col], M[piv] = M[piv], M[col]
            pv = M[col][col]
            if abs(pv) < 1e-10:
                continue
            for j in range(col, n + 1):
                M[col][j] /= pv
            for r in range(n):
                if r != col and M[r][col] != 0:
                    factor = M[r][col]
                    for j in range(col, n + 1):
                        M[r][j] -= factor * M[col][j]
        return [M[i][n] for i in range(n)]

    def predict(self, x: float) -> float:
        if self.coefficients is None or not self.knots:
            return 0.0
        knots = self.knots
        row = [1.0, x]
        for k in range(len(knots) - 2):
            row.append(self._spline_basis(x, knots, k))
        return sum(c * row[i] for i, c in enumerate(self.coefficients))


class DoseEffectAnalyzer:

    DOSAGE_RANGE = {
        "default": (3.0, 15.0),
        "附子": (3.0, 30.0),
        "麻黄": (3.0, 12.0),
        "桂枝": (3.0, 15.0),
        "甘草": (3.0, 10.0),
        "人参": (3.0, 10.0),
        "黄芪": (10.0, 60.0),
        "石膏": (15.0, 60.0),
        "大黄": (3.0, 12.0),
        "黄连": (2.0, 8.0),
        "细辛": (1.0, 3.0),
        "马钱子": (0.3, 0.6),
        "朱砂": (0.1, 0.5),
        "雄黄": (0.05, 0.2),
        "白术": (6.0, 15.0),
        "茯苓": (9.0, 15.0),
        "当归": (6.0, 12.0),
        "白芍": (6.0, 15.0),
        "川芎": (3.0, 10.0),
        "生地黄": (10.0, 30.0),
        "熟地黄": (10.0, 30.0),
        "半夏": (3.0, 10.0),
        "陈皮": (3.0, 10.0),
        "枳实": (3.0, 10.0),
        "厚朴": (3.0, 10.0),
        "柴胡": (3.0, 10.0),
        "黄芩": (6.0, 15.0),
        "栀子": (6.0, 10.0),
        "知母": (6.0, 12.0),
        "麦冬": (6.0, 15.0),
        "五味子": (2.0, 6.0),
        "杏仁": (3.0, 10.0),
        "桔梗": (3.0, 10.0),
        "牛膝": (6.0, 15.0),
        "桃仁": (5.0, 10.0),
        "红花": (3.0, 10.0),
        "丹参": (10.0, 30.0),
        "赤芍": (6.0, 15.0),
        "泽泻": (6.0, 15.0),
        "车前子": (9.0, 15.0),
        "防风": (6.0, 10.0),
        "羌活": (3.0, 10.0),
        "独活": (3.0, 10.0),
        "秦艽": (3.0, 10.0),
        "威灵仙": (6.0, 10.0),
        "木香": (3.0, 6.0),
        "香附": (6.0, 10.0),
        "乌头": (1.5, 5.0),
        "蟾酥": (0.015, 0.03),
        "巴豆": (0.1, 0.3),
        "甘遂": (0.5, 1.5),
        "大戟": (1.0, 3.0),
        "芫花": (1.0, 3.0),
    }

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def _dosing_bell_curve(self, herb: str) -> Tuple[float, float, float]:
        lo, hi = self.DOSAGE_RANGE.get(herb, self.DOSAGE_RANGE["default"])
        center = (lo + hi) / 2
        sigma = (hi - lo) / 4
        peak = 0.6 + self.rng.uniform(0.15, 0.3)
        return center, sigma, peak

    def simulate_observations(self, herb_name: str,
                              n_per_bin: int = 8,
                              bins: int = 7) -> List[Dict[str, Any]]:
        lo, hi = self.DOSAGE_RANGE.get(herb_name, self.DOSAGE_RANGE["default"])
        center, sigma, peak = self._dosing_bell_curve(herb_name)
        dosages = [lo + (hi - lo) * i / (bins - 1) for i in range(bins)]
        data = []
        for d in dosages:
            ideal = peak * math.exp(-((d - center) ** 2) / (2 * sigma * sigma))
            toxicity_factor = 0.0
            if d > hi * 0.85:
                toxicity_factor = ((d - hi * 0.85) / (hi * 0.15 + 1e-6)) * 0.5
            min_ = 0.1
            efficacy = max(min_, min(0.98, ideal * (1 + self.rng.uniform(-0.15, 0.15)) - toxicity_factor))
            sample_n = n_per_bin + self.rng.randint(-2, 5)
            se = max(0.02, efficacy * (1 - efficacy) / math.sqrt(sample_n))
            data.append({
                "herb_name": herb_name,
                "dosage_g": round(d, 2),
                "avg_efficacy": round(efficacy, 4),
                "sample_size": sample_n,
                "std_error": round(se, 4),
            })
        return data

    def fit_curve(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        xs = [o["dosage_g"] for o in observations]
        ys = [o["avg_efficacy"] for o in observations]
        ws = [o["sample_size"] for o in observations]
        model = RestrictedCubicSpline(nk=4)
        model.fit(xs, ys, ws)
        fine_xs = [min(xs) + (max(xs) - min(xs)) * i / 200 for i in range(201)]
        fine_ys = [model.predict(x) for x in fine_xs]
        best_idx = max(range(len(fine_ys)), key=lambda i: fine_ys[i])
        best_x = fine_xs[best_idx]
        threshold = fine_ys[best_idx] * 0.9
        left = best_x
        for i in range(best_idx, -1, -1):
            if fine_ys[i] < threshold:
                left = fine_xs[i]
                break
        right = best_x
        for i in range(best_idx, len(fine_ys)):
            if fine_ys[i] < threshold:
                right = fine_xs[i]
                break
        points = [
            {
                "herb_name": observations[0]["herb_name"],
                "dosage_g": round(fine_xs[i], 3),
                "avg_efficacy": round(fine_ys[i], 4),
                "sample_size": 0,
                "std_error": 0.0,
            }
            for i in range(0, 201, 10)
        ]
        for o in observations:
            points.append(o)
        points.sort(key=lambda p: p["dosage_g"])
        return {
            "herb_name": observations[0]["herb_name"],
            "points": points,
            "optimal_dose_range": [round(left, 2), round(right, 2)],
            "model_type": "RestrictedCubicSpline(k=4)",
            "r_squared": round(model.r_squared, 4),
            "knots": [round(k, 3) for k in (model.knots or [])],
        }

    @staticmethod
    def dose_meta_analysis(studies: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not studies:
            return {"pooled_effect": 0.0, "ci": [0.0, 0.0], "i_squared": 0.0}
        es = [s["effect_size"] for s in studies]
        vi = [s["variance"] for s in studies]
        wi = [1 / v for v in vi]
        q = sum(w * (e - sum(w * e for w, e in zip(wi, es)) / sum(wi)) ** 2
                for e, w in zip(es, wi))
        k = len(studies)
        i2 = max(0.0, (q - (k - 1)) / q * 100.0) if q > 0 else 0.0
        tau2 = max(0.0, (q - (k - 1)) / (sum(wi) - sum(w * w for w in wi) / sum(wi)))
        w_re = [1 / (v + tau2) for v in vi]
        pooled = sum(w * e for w, e in zip(w_re, es)) / sum(w_re)
        se = math.sqrt(1 / sum(w_re))
        ci = [pooled - 1.96 * se, pooled + 1.96 * se]
        z = pooled / se if se > 0 else 0.0
        p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        return {
            "pooled_effect_size": round(pooled, 4),
            "ci_95": [round(ci[0], 4), round(ci[1], 4)],
            "p_value": round(p_val, 6),
            "i_squared": round(i2, 2),
            "tau_squared": round(tau2, 6),
            "studies_included": k,
        }
