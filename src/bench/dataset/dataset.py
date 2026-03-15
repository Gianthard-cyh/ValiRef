"""Benchmark dataset class."""
import csv
from typing import List

from src.core.logger import logger
from src.bench.crawler import PaperCrawler
from src.bench.schema import Paper


class BenchmarkDataset:
    def __init__(self, dataset: List[Paper]):
        self.dataset = dataset
        self.crawler = PaperCrawler()

    def __len__(self):
        return len(self.dataset)

    def to_csv(self, file_path: str):
        """
        Export the dataset to a CSV file.
        """
        if not self.dataset:
            logger.warning("Dataset is empty. Nothing to export.")
            return

        fieldnames = self.dataset[0].model_dump().keys()

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for paper in self.dataset:
                    row = paper.model_dump()
                    # Handle list fields for CSV (e.g., authors, claims)
                    for key, value in row.items():
                        if isinstance(value, list):
                            row[key] = "; ".join(map(str, value))
                    writer.writerow(row)
            logger.info(f"Dataset exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export dataset to CSV: {e}")
