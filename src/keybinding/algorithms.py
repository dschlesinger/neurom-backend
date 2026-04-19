import math
from dataclasses import dataclass
from itertools import groupby
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np
import scipy
from dtaidistance import dtw
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.svm import SVC


class AlgorithmBase:
    name: str = "base"
    input_type: str = "vector"  # "vector" or "window"

    def fit(self, x: np.ndarray, y: List[str]) -> None:
        raise NotImplementedError

    def predict(self, x: np.ndarray) -> str:
        raise NotImplementedError


def pad_center(d: List[np.ndarray], max_len: Optional[int] = None) -> np.ndarray:
    # Convert samples x channels -> channels x samples
    windows = [np.array(di).T for di in d]
    max_len = max(*[di.shape[1] for di in windows], max_len or 0)

    padded = []

    for di in windows:
        pad_needed = max_len - di.shape[1]
        left_pad, right_pad = pad_needed // 2, math.ceil(pad_needed / 2)
        p = np.pad(di, ((0, 0), (left_pad, right_pad)), mode="mean")
        padded.append(p)

    return np.array(padded)


def pad_or_trim_center(window: np.ndarray, target_len: int) -> np.ndarray:
    if window.shape[1] == target_len:
        return window
    if window.shape[1] > target_len:
        diff = window.shape[1] - target_len
        left = diff // 2
        right = left + target_len
        return window[:, left:right]

    pad_needed = target_len - window.shape[1]
    left_pad, right_pad = pad_needed // 2, math.ceil(pad_needed / 2)
    return np.pad(window, ((0, 0), (left_pad, right_pad)), mode="mean")


def _dtw_distance_sakoe_chiba(x: np.ndarray, y: np.ndarray, band: int) -> float:
    n = x.shape[0]
    m = y.shape[0]
    band = max(band, abs(n - m))

    dtw_matrix = np.full((n + 1, m + 1), np.inf, dtype=float)
    dtw_matrix[0, 0] = 0.0

    for i in range(1, n + 1):
        j_start = max(1, i - band)
        j_end = min(m, i + band) + 1
        for j in range(j_start, j_end):
            cost = abs(x[i - 1] - y[j - 1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],
                dtw_matrix[i, j - 1],
                dtw_matrix[i - 1, j - 1],
            )

    return dtw_matrix[n, m]


def _dtw_distance(x: np.ndarray, y: np.ndarray, band: Optional[int] = None) -> float:
    if band is None:
        return dtw.distance_fast(x, y)

    try:
        return dtw.distance_fast(x, y, window=band)
    except TypeError:
        return _dtw_distance_sakoe_chiba(x, y, band)


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 1.0
    return 1.0 - float(np.dot(a, b) / denom)


class DtwAlgorithm(AlgorithmBase):
    name = "dtw"
    input_type = "window"

    def __init__(self, continuity_threshold: float = 275.0, band: Optional[int] = None) -> None:
        self.continuity_threshold = continuity_threshold
        self.band = band
        self._windows: Optional[np.ndarray] = None
        self._labels: List[str] = []

    def fit(self, x: np.ndarray, y: List[str]) -> None:
        self._windows = x
        self._labels = y

    def predict(self, x: np.ndarray) -> str:
        if self._windows is None:
            raise ValueError("DTW model not fitted")

        values = []
        for window in self._windows:
            values.append(
                sum(_dtw_distance(xi, wi, self.band) for xi, wi in zip(x, window))
            )

        cls_choice = []
        cls_values = []

        paired = sorted(list(zip(values, self._labels)), key=lambda a: a[1])
        for cls, vls in groupby(paired, key=lambda a: a[1]):
            vls = [v[0] for v in list(vls)]
            cls_choice.append(cls)
            cls_values.append(sum(vls) / len(vls))

        scores = np.array(cls_values)
        cont_score = scores.min() / x.shape[0]

        if cont_score > self.continuity_threshold:
            print("Continuity score exceeds threshold may be false emission")

        scores = (scores - scores.mean()) / scores.std()
        probs = scipy.special.softmax(scores)

        for pro, cls in zip(probs, cls_choice):
            print(f"\t{cls}: {pro.item():.2f}")

        return cls_choice[probs.argmin().item()]


class ConstrainedDtwAlgorithm(DtwAlgorithm):
    name = "constrained_dtw"


class TemplateMatchingAlgorithm(AlgorithmBase):
    name = "template"
    input_type = "vector"

    def __init__(self, metric: str = "euclidean") -> None:
        self.metric = metric
        self._prototypes: Dict[str, np.ndarray] = {}

    def fit(self, x: np.ndarray, y: List[str]) -> None:
        by_class: Dict[str, List[np.ndarray]] = {}
        for vec, cls in zip(x, y):
            by_class.setdefault(cls, []).append(vec)

        for cls, vecs in by_class.items():
            self._prototypes[cls] = np.mean(vecs, axis=0)

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        if self.metric == "cosine":
            return _cosine_distance(a, b)
        return float(np.linalg.norm(a - b))

    def predict(self, x: np.ndarray) -> str:
        best_cls = None
        best_score = float("inf")

        for cls, proto in self._prototypes.items():
            score = self._distance(x, proto)
            if score < best_score:
                best_score = score
                best_cls = cls

        if best_cls is None:
            raise ValueError("Template model not fitted")

        return best_cls


class PrototypeMatchingAlgorithm(TemplateMatchingAlgorithm):
    name = "prototype"

    def fit(self, x: np.ndarray, y: List[str]) -> None:
        by_class: Dict[str, List[np.ndarray]] = {}
        for vec, cls in zip(x, y):
            by_class.setdefault(cls, []).append(vec)

        for cls, vecs in by_class.items():
            self._prototypes[cls] = np.median(vecs, axis=0)


class SvmAlgorithm(AlgorithmBase):
    name = "svm"
    input_type = "vector"

    def __init__(self, kernel: str = "rbf") -> None:
        self._model = SVC(kernel=kernel, gamma="scale")

    def fit(self, x: np.ndarray, y: List[str]) -> None:
        self._model.fit(x, y)

    def predict(self, x: np.ndarray) -> str:
        return str(self._model.predict([x])[0])


class LdaAlgorithm(AlgorithmBase):
    name = "lda"
    input_type = "vector"

    def __init__(self) -> None:
        self._model = LinearDiscriminantAnalysis()

    def fit(self, x: np.ndarray, y: List[str]) -> None:
        self._model.fit(x, y)

    def predict(self, x: np.ndarray) -> str:
        return str(self._model.predict([x])[0])


@dataclass
class AlgorithmSpec:
    constructor: Callable[[Dict], AlgorithmBase]
    aliases: Iterable[str]


def build_algorithm_registry() -> Dict[str, callable]:
    registry: Dict[str, callable] = {}

    def register(spec: AlgorithmSpec) -> None:
        for alias in spec.aliases:
            registry[alias] = spec.constructor

    register(
        AlgorithmSpec(
            constructor=lambda params: DtwAlgorithm(
                continuity_threshold=params.get("continuity_threshold", 275.0)
            ),
            aliases=["dtw"],
        )
    )
    register(
        AlgorithmSpec(
            constructor=lambda params: ConstrainedDtwAlgorithm(
                continuity_threshold=params.get("continuity_threshold", 275.0),
                band=params.get("band"),
            ),
            aliases=["constrained_dtw", "dtw_constrained"],
        )
    )
    register(
        AlgorithmSpec(
            constructor=lambda params: TemplateMatchingAlgorithm(
                metric=params.get("metric", "euclidean")
            ),
            aliases=["template", "template_matching"],
        )
    )
    register(
        AlgorithmSpec(
            constructor=lambda params: PrototypeMatchingAlgorithm(
                metric=params.get("metric", "euclidean")
            ),
            aliases=["prototype", "shapelet", "shapelet_prototype"],
        )
    )
    register(
        AlgorithmSpec(
            constructor=lambda params: SvmAlgorithm(
                kernel=params.get("kernel", "rbf")
            ),
            aliases=["svm"],
        )
    )
    register(
        AlgorithmSpec(
            constructor=lambda params: LdaAlgorithm(),
            aliases=["lda"],
        )
    )

    return registry


def create_algorithm(name: str, params: Optional[Dict] = None) -> AlgorithmBase:
    params = params or {}
    registry = build_algorithm_registry()
    if name not in registry:
        raise ValueError(f"Unknown algorithm '{name}'")

    return registry[name](params)
