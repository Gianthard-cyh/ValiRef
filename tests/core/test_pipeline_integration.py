import pytest
from pathlib import Path
from src.core.pipeline import ValidationPipeline
import asyncio


@pytest.mark.integration
def test_pipeline_pdf_processing():
    # Locate the test PDF
    pdf_path = (
        Path(__file__).parent.parent / "data" / "11262_TamperTok_Forensics_Driv.pdf"
    )
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found at {pdf_path}")

    print(f"Testing with PDF: {pdf_path}")

    pipeline = ValidationPipeline()

    # Run pipeline with a small number of workers to avoid overwhelming the test environment
    # The original script used 50, let's use 50 as requested
    results = asyncio.run(pipeline.process_pdf(str(pdf_path), max_workers=50))

    assert results is not None
    assert "references_count" in results
    assert "validated_count" in results
    assert "results" in results

    # Check if we got any results
    assert results["references_count"] > 0
    assert len(results["results"]) > 0

    # Check structure of results
    first_result = results["results"][0]
    assert "paper" in first_result
    assert "validation" in first_result

    validation = first_result["validation"]
    assert "is_hallucination" in validation
    assert "confidence" in validation
    assert "evidence" in validation

    # Print summary (visible with pytest -s)
    real_count = sum(
        1
        for r in results["results"]
        if r["validation"].get("is_hallucination") is False
    )
    fake_count = sum(
        1 for r in results["results"] if r["validation"].get("is_hallucination") is True
    )
    errors = sum(
        1 for r in results["results"] if r["validation"].get("is_hallucination") is None
    )

    print("\nPipeline Test Summary:")
    print(f"Total References: {results['references_count']}")
    print(f"Real: {real_count}")
    print(f"Hallucinations: {fake_count}")
    print(f"Errors: {errors}")
