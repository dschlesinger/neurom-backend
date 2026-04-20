import argparse
import glob
import json
import io
import time
from contextlib import redirect_stdout
from typing import Dict, List

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from tqdm import tqdm

from keybinding.model import Model
from cli.config import Settings
from keybinding.algorithms import build_algorithm_registry, pad_or_trim_center


def load_file_list(test_mode: bool) -> List[str]:
    if test_mode:
        return ["data_store/Basic 0.32.json"]
    return sorted(glob.glob("data_store/*.json"))


def normalize_label(label: str) -> str:
    return label.strip()


def predict_with_train_state(model: Model, train_state, datapoint) -> str:
    x = datapoint.anom.data.T
    x = pad_or_trim_center(x, train_state.max_len)

    if train_state.algorithm.input_type == "window":
        return train_state.algorithm.predict(x)

    flat = x.reshape(-1)
    if train_state.pca is not None:
        flat = train_state.pca.transform([flat])[0]
    return train_state.algorithm.predict(flat)


def evaluate_algorithm(
    algorithm_name: str, filepaths: List[str], pca_enabled: bool
) -> Dict[str, float]:
    prev_pca = Settings.PCA_ENABLE
    Settings.PCA_ENABLE = pca_enabled
    model = Model(algorithm_name=algorithm_name)
    model.load_data(filepaths)

    y_true: List[str] = []
    y_pred: List[str] = []

    datapoints = model.datapoints or []

    inference_time_s = 0.0
    fallback_count = 0

    for idx, dp in enumerate(tqdm(datapoints, desc=f"Testing {algorithm_name}", leave=False)):
        train_data = [d for j, d in enumerate(datapoints) if j != idx]
        try:
            train_state = model._prepare_training(train_data)
        except Exception as exc:
            msg = str(exc).lower()
            if "svd" in msg and "converge" in msg:
                fallback_count += 1
                prev_pca = Settings.PCA_ENABLE
                Settings.PCA_ENABLE = False
                try:
                    train_state = model._prepare_training(train_data)
                finally:
                    Settings.PCA_ENABLE = prev_pca
            else:
                raise
        if train_state is None:
            continue

        with redirect_stdout(io.StringIO()):
            start = time.perf_counter()
            guess = predict_with_train_state(model, train_state, dp)
            inference_time_s += time.perf_counter() - start
        y_true.append(normalize_label(dp.classification))
        y_pred.append(normalize_label(guess))

    Settings.PCA_ENABLE = prev_pca

    if not y_true:
        return {
            "count": 0,
            "accuracy": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "f1_macro": 0.0,
            "f1_weighted": 0.0,
            "inference_time_s": 0.0,
            "inference_avg_ms": 0.0,
            "pca_enabled": pca_enabled,
            "pca_fallbacks": fallback_count,
        }

    return {
        "count": len(y_true),
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "inference_time_s": inference_time_s,
        "inference_avg_ms": (inference_time_s / len(y_true)) * 1000.0,
        "pca_enabled": pca_enabled,
        "pca_fallbacks": fallback_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate artifact algorithms.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use only data_store/Basic 0.32.json for a quick demo run.",
    )
    parser.add_argument(
        "--no-compare-pca",
        action="store_true",
        help="Disable running evaluation with PCA on and off.",
    )
    args = parser.parse_args()

    filepaths = load_file_list(args.test)
    if not filepaths:
        print("No data_store/*.json files found.")
        return

    registry = build_algorithm_registry()
    algo_names = sorted(set(registry.keys()))

    print("Data files:")
    for path in filepaths:
        print(f"  - {path}")

    pca_modes = [True, False]
    if args.no_compare_pca:
        pca_modes = [Settings.PCA_ENABLE]

    print("\nResults:")
    for name in algo_names:
        for pca_enabled in pca_modes:
            metrics = evaluate_algorithm(name, filepaths, pca_enabled)
            pca_label = "on" if pca_enabled else "off"
            print(f"\nAlgorithm: {name} (PCA {pca_label})")
            print(f"  samples: {metrics['count']}")
            print(f"  accuracy: {metrics['accuracy']:.4f}")
            print(f"  precision_macro: {metrics['precision_macro']:.4f}")
            print(f"  recall_macro: {metrics['recall_macro']:.4f}")
            print(f"  f1_macro: {metrics['f1_macro']:.4f}")
            print(f"  f1_weighted: {metrics['f1_weighted']:.4f}")
            print(f"  inference_time_s: {metrics['inference_time_s']:.4f}")
            print(f"  inference_avg_ms: {metrics['inference_avg_ms']:.3f}")
            print(f"  pca_fallbacks: {metrics['pca_fallbacks']}")


if __name__ == "__main__":
    main()
