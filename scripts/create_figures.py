from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "artifacts" / "results"
FIGURES = ROOT / "artifacts" / "figures"
MODELS = ("cae", "padim", "patchcore", "stfpm")
CATEGORIES = ("bottle", "tile", "transistor")
COLORS = ("#4E79A7", "#59A14F", "#F28E2B", "#E15759")


def setup() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial"],
        "axes.unicode_minus": False,
        "figure.dpi": 150,
        "savefig.dpi": 220,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def model_comparison() -> None:
    rows = list(csv.DictReader((RESULTS / "model_averages.csv").open(encoding="utf-8-sig")))
    names = [row["model"].upper() for row in rows]
    metrics = [("image_auroc", "图像AUROC"), ("pixel_auroc", "像素AUROC"), ("f1", "F1")]
    x = np.arange(len(names))
    width = 0.23
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for index, (key, label) in enumerate(metrics):
        values = [float(row[key]) for row in rows]
        bars = ax.bar(x + (index - 1) * width, values, width, label=label, color=COLORS[index])
        ax.bar_label(bars, fmt="%.3f", fontsize=8, padding=2)
    ax.set_xticks(x, names)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("平均指标值")
    ax.set_title("四种缺陷检测模型综合性能对比")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=3, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIGURES / "model_average_comparison.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 4.7))
    values = [float(row["inference_ms"]) for row in rows]
    bars = ax.bar(names, values, color=COLORS)
    ax.bar_label(bars, fmt="%.1f ms", padding=3)
    ax.set_ylabel("单张平均推理耗时（ms）")
    ax.set_title("四种模型推理效率对比")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "inference_latency.png", bbox_inches="tight")
    plt.close(fig)


def training_curves() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.3))
    for model, ax, title in (("cae", axes[0], "CAE训练损失"), ("stfpm", axes[1], "STFPM训练损失")):
        for category, color in zip(CATEGORIES, COLORS):
            path = ROOT / "artifacts" / "models" / model / f"{category}.pt.json"
            losses = load_json(path)["training"].get("epoch_losses", [])
            ax.plot(range(1, len(losses) + 1), losses, marker="o", linewidth=2, markersize=4, label=category, color=color)
        ax.set_title(title)
        ax.set_xlabel("训练轮次")
        ax.set_ylabel("Loss")
        ax.grid(alpha=0.25)
        ax.legend()
    fig.suptitle("深度模型训练收敛曲线", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "training_loss_curves.png", bbox_inches="tight")
    plt.close(fig)


def ablation_figures() -> None:
    before, after = [], []
    for category in CATEGORIES:
        folder = RESULTS / "patchcore" / category
        before.append(float(load_json(folder / "metrics_before_normalization.json")["image_auroc"]))
        after.append(float(load_json(folder / "metrics.json")["image_auroc"]))
    x = np.arange(len(CATEGORIES))
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    bars1 = ax.bar(x - 0.18, before, 0.36, label="归一化前", color="#BAB0AC")
    bars2 = ax.bar(x + 0.18, after, 0.36, label="L2归一化后", color="#4E79A7")
    ax.bar_label(bars1, fmt="%.3f", fontsize=9)
    ax.bar_label(bars2, fmt="%.3f", fontsize=9)
    ax.set_xticks(x, CATEGORIES)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("图像AUROC")
    ax.set_title("PatchCore特征归一化消融结果")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "patchcore_ablation.png", bbox_inches="tight")
    plt.close(fig)

    names = ("bottle", "tile", "transistor")
    q99 = [float(load_json(RESULTS / "stfpm" / name / "metrics_quantile_099.json")["f1"]) for name in names]
    final = [float(load_json(RESULTS / "stfpm" / name / "metrics.json")["f1"]) for name in names]
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    bars1 = ax.bar(x - 0.18, q99, 0.36, label="校准前", color="#BAB0AC")
    bars2 = ax.bar(x + 0.18, final, 0.36, label="校准后", color="#E15759")
    ax.bar_label(bars1, fmt="%.3f", fontsize=9)
    ax.bar_label(bars2, fmt="%.3f", fontsize=9)
    ax.set_xticks(x, names)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("F1")
    ax.set_title("STFPM正常样本阈值校准结果")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / "stfpm_threshold_ablation.png", bbox_inches="tight")
    plt.close(fig)


def detection_montage() -> None:
    report = load_json(ROOT / "artifacts" / "system_acceptance.json")
    paths = [ROOT / report["sample"]]
    titles = ["原始缺陷图"]
    for item in report["detections"]:
        relative = item["heatmap_url"].removeprefix("/storage/")
        paths.append(ROOT / "backend" / "storage" / relative)
        titles.append(item["model"].upper())
    fig, axes = plt.subplots(1, len(paths), figsize=(15.5, 3.6))
    for ax, path, title in zip(axes, paths, titles):
        with Image.open(path) as image:
            ax.imshow(image.convert("RGB"))
        ax.set_title(title)
        ax.axis("off")
    fig.suptitle("同一缺陷图在四种模型下的定位结果", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIGURES / "system_detection_montage.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    setup()
    model_comparison()
    training_curves()
    ablation_figures()
    detection_montage()
    print(FIGURES)


if __name__ == "__main__":
    main()
