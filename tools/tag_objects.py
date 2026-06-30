from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft ObjectCatalog review rows.")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/puzzle/object_review.csv"))
    args = parser.parse_args()

    labels = [
        line.strip()
        for line in args.labels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "approved",
                "object_id",
                "canonical_label",
                "aliases_json",
                "shape_vec_json",
                "malleability",
                "evocability",
                "category",
                "dominant_colors_json",
                "source",
                "status",
            ],
        )
        writer.writeheader()
        for label in labels:
            writer.writerow(draft_row(label))
    print(f"Wrote review draft to {args.out}")


def draft_row(label: str) -> dict:
    object_id = label.lower().replace(" ", "_").replace("-", "_")
    return {
        "approved": "false",
        "object_id": object_id,
        "canonical_label": label,
        "aliases_json": json.dumps([]),
        "shape_vec_json": json.dumps([0.5, 0.5, 0.5, 0.0, 0.5]),
        "malleability": "0.5",
        "evocability": "0.5",
        "category": "unknown",
        "dominant_colors_json": json.dumps([]),
        "source": "llm_proposed",
        "status": "active",
    }


if __name__ == "__main__":
    main()
