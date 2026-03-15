"""Run a single sample from dataset through detector with LangSmith tracing."""
import os
import asyncio
import csv

# Configure LangSmith tracing BEFORE importing langchain
# Set these environment variables before running:
# export LANGSMITH_API_KEY="your-api-key"
# export LANGSMITH_PROJECT="ValiRef"
# export LANGSMITH_TRACING="true"
os.environ.setdefault("LANGSMITH_PROJECT", "ValiRef")
os.environ.setdefault("LANGSMITH_TRACING", "true")
os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

if not os.environ.get("LANGSMITH_API_KEY"):
    raise ValueError("Please set LANGSMITH_API_KEY environment variable")

from src.core.detector import HallucinationDetector
from src.bench.schema import Paper


def load_sample_from_dataset(path: str, index: int = 0) -> Paper:
    """Load a single sample from dataset (same as benchmark)."""
    with open(path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for i, row in enumerate(reader):
            if i == index:
                # Parse list fields (same as benchmark runner)
                authors = []
                if row.get("authors"):
                    authors = [a.strip() for a in row["authors"].split(";") if a.strip()]

                claims = []
                if row.get("claims"):
                    claims = [c.strip() for c in row["claims"].split(";") if c.strip()]

                paper = Paper(
                    source=row.get("source", ""),
                    id=row.get("id", ""),
                    title=row.get("title", ""),
                    abstract=row.get("abstract", ""),
                    authors=authors,
                    published_date=row.get("published_date", ""),
                    updated_date=row.get("updated_date") or None,
                    url=row.get("url", ""),
                    pdf_url=row.get("pdf_url") or None,
                    claims=claims,
                    hallucination_type=row.get("hallucination_type") or None,
                    original_paper_id=row.get("original_paper_id") or None,
                )
                return paper
    raise ValueError(f"Dataset has fewer than {index + 1} rows")


def get_ground_truth_type(paper: Paper) -> str:
    """Same logic as benchmark runner."""
    if not paper.hallucination_type:
        return "Real"
    type_mapping = {
        "fabrication": "Fabrication",
        "attributionerror": "AttributionError",
        "attribution_error": "AttributionError",
        "irrelevance": "Irrelevance",
        "counterfactual": "Counterfactual",
    }
    normalized = paper.hallucination_type.strip()
    return type_mapping.get(normalized.lower(), normalized)


async def main():
    dataset_path = "/home/cyh/ValiRef/data/dataset.csv"

    # Load sample at index 2000 (first sample with claims, which is Real ground truth)
    # Actually let me find a Real sample first
    print("Loading samples to find a Real one...")

    # Find first Real sample (ground truth Real based on hallucination_type being empty)
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        real_indices = []
        for i, row in enumerate(reader):
            if not row.get("hallucination_type", "").strip():
                real_indices.append(i)
            if len(real_indices) >= 10:
                break

    print(f"Found {len(real_indices)} Real samples at indices: {real_indices[:5]}...")

    # Let's use the first Real sample
    sample_index = real_indices[0] if real_indices else 0
    paper = load_sample_from_dataset(dataset_path, sample_index)

    ground_truth = get_ground_truth_type(paper)

    print("\n" + "=" * 60)
    print("SAMPLE INFO (from dataset)")
    print("=" * 60)
    print(f"Index: {sample_index}")
    print(f"Ground Truth: {ground_truth}")
    print(f"\nID: {paper.id}")
    print(f"Title: {paper.title}")
    print(f"Authors: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}")
    print(f"Claims: {len(paper.claims)} claims")
    if paper.claims:
        for i, claim in enumerate(paper.claims[:2], 1):
            print(f"  {i}. {claim[:100]}...")
    else:
        print("  (no claims)")
    print("=" * 60)
    print()

    # Initialize detector
    print("Initializing detector...")
    detector = HallucinationDetector()

    # Run detection
    print("Running detection (with LangSmith tracing)...\n")
    result = await detector.acheck_reference(paper)

    print("\n" + "=" * 60)
    print("DETECTION RESULT")
    print("=" * 60)
    print(f"Ground Truth: {ground_truth}")
    print(f"Prediction: {result.hallucination_type}")
    print(f"Confidence: {result.confidence}")
    print(f"Correct: {result.hallucination_type == ground_truth}")
    print(f"\nReasoning:\n{result.reasoning}")
    print(f"\nEvidence:")
    for url in result.evidence:
        print(f"  - {url}")

    print("\n" + "=" * 60)
    print("LangSmith Project: ValiRef")
    print("Check traces at: https://smith.langchain.com")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
