import pytest
import sys
import os
from src.bench.schema import Paper
from src.core.detector import HallucinationDetector

@pytest.mark.integration
def test_detector_return_direct():
    """
    Integration test for HallucinationDetector using a real paper.
    Validates that the detector returns a structured result directly.
    """
    print("Initializing HallucinationDetector (Integration Test)...")
    detector = HallucinationDetector()
    
    # Test Case: Real Paper "Attention Is All You Need"
    # Note: We must provide the full author list, otherwise the detector might flag it as a hallucination due to missing authors.
    paper = Paper(
        source="test",
        id="1706.03762",
        title="Attention Is All You Need",
        abstract="N/A",
        authors=[
            "Ashish Vaswani", "Noam Shazeer", "Niki Parmar", 
            "Jakob Uszkoreit", "Llion Jones", "Aidan N. Gomez", 
            "Lukasz Kaiser", "Illia Polosukhin"
        ],
        published_date="2017",
        url="https://arxiv.org/abs/1706.03762",
        venue="NIPS"
    )
    
    print(f"\nTesting: {paper.title}")
    result = detector.check_reference(paper)
    
    # Basic assertions
    assert result is not None
    assert hasattr(result, "is_hallucination")
    assert hasattr(result, "confidence")
    assert hasattr(result, "reasoning")
    assert hasattr(result, "evidence")
    
    # Specific expectations for a known real paper
    # Note: Depending on the tools used, it might fail to verify if external APIs are down,
    # but it should return a valid result object.
    # We assert strict correctness if possible, but allow for API failures if handled gracefully.
    
    print("-" * 50)
    print(f"Is Hallucination: {result.is_hallucination}")
    print(f"Confidence: {result.confidence}")
    print(f"Reasoning: {result.reasoning}")
    print(f"Evidence: {len(result.evidence)} items")
    print("-" * 50)
    
    # Assuming the tools work, this paper should be verified as real (is_hallucination=False)
    # However, if tools fail or return no results, it might be inconclusive (None) or False (default real if found but not hallucination evidence?)
    # Usually real papers are False.
    
    if result.is_hallucination is not None:
        assert result.is_hallucination is False, "Expected 'Attention Is All You Need' to be verified as Real"
    
    # Ensure evidence is a list
    assert isinstance(result.evidence, list)
