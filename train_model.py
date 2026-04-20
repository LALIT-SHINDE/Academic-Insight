from __future__ import annotations

import csv
import pickle
import random
from pathlib import Path

from model_utils import StudentPerformanceKNN


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
DATASET_PATH = BASE_DIR / "students.csv"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def build_training_data(size: int = 240) -> tuple[list[list[float]], list[int]]:
    random.seed(42)

    samples: list[list[float]] = []
    labels: list[int] = []

    for _ in range(size):
        attendance = round(random.uniform(45, 100), 2)
        mid_marks = round(random.uniform(35, 100), 2)
        assignments = round(random.uniform(40, 100), 2)
        study_hours = round(random.uniform(0.5, 10), 2)

        normalized_hours = clamp((study_hours / 8) * 100, 0, 100)
        weighted_score = (
            attendance * 0.25
            + mid_marks * 0.35
            + assignments * 0.25
            + normalized_hours * 0.15
        )

        weighted_score += random.uniform(-4, 4)

        if weighted_score >= 85:
            label = 3
        elif weighted_score >= 70:
            label = 2
        elif weighted_score >= 55:
            label = 1
        else:
            label = 0

        samples.append([attendance, mid_marks, assignments, study_hours])
        labels.append(label)

    return samples, labels


def label_to_int(label: str) -> int:
    mapping = {
        "Needs Improvement": 0,
        "Average": 1,
        "Good": 2,
        "Excellent": 3,
    }

    normalized = label.strip()
    if normalized not in mapping:
        raise ValueError(
            "performance_label must be one of: Needs Improvement, Average, Good, Excellent."
        )

    return mapping[normalized]


def load_csv_training_data(path: Path) -> tuple[list[list[float]], list[int]]:
    samples: list[list[float]] = []
    labels: list[int] = []

    with path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        required_fields = {
            "attendance",
            "mid_marks",
            "assignments",
            "study_hours",
            "performance_label",
        }

        if reader.fieldnames is None or not required_fields.issubset(set(reader.fieldnames)):
            raise ValueError(
                "students.csv must include attendance, mid_marks, assignments, study_hours, and performance_label columns."
            )

        for row in reader:
            samples.append(
                [
                    float(row["attendance"]),
                    float(row["mid_marks"]),
                    float(row["assignments"]),
                    float(row["study_hours"]),
                ]
            )
            labels.append(label_to_int(row["performance_label"]))

    if not samples:
        raise ValueError("students.csv must contain at least one student record.")

    return samples, labels


def main() -> None:
    if DATASET_PATH.exists():
        samples, labels = load_csv_training_data(DATASET_PATH)
    else:
        samples, labels = build_training_data()

    model = StudentPerformanceKNN(neighbors=7).fit(samples, labels)

    with MODEL_PATH.open("wb") as model_file:
        pickle.dump(model, model_file)

    print(f"Saved trained model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
