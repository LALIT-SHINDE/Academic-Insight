from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt


@dataclass
class StudentPerformanceKNN:
    """A tiny dependency-free KNN classifier for student performance."""

    neighbors: int = 5
    samples: list[list[float]] = field(default_factory=list)
    labels: list[int] = field(default_factory=list)

    def fit(self, samples: list[list[float]], labels: list[int]) -> "StudentPerformanceKNN":
        if not samples or not labels:
            raise ValueError("Training data cannot be empty.")
        if len(samples) != len(labels):
            raise ValueError("Training samples and labels must have the same length.")

        self.samples = samples
        self.labels = labels
        return self

    def predict_one(self, features: list[float]) -> int:
        if not self.samples:
            raise ValueError("Model has not been trained.")

        distances: list[tuple[float, int]] = []
        for sample, label in zip(self.samples, self.labels):
            distance = sqrt(sum((a - b) ** 2 for a, b in zip(sample, features)))
            distances.append((distance, label))

        distances.sort(key=lambda item: item[0])
        nearest = distances[: self.neighbors]


        votes: dict[int, int] = {}
        for _, label in nearest:
            votes[label] = votes.get(label, 0) + 1

        # Break ties by choosing the label with more votes, then higher label.
        return max(votes.items(), key=lambda item: (item[1], item[0]))[0]

    def predict(self, samples: list[list[float]]) -> list[int]:
        return [self.predict_one(sample) for sample in samples]
