#!/usr/bin/env python3
"""Test a single Real sample with verbose Agent output."""
import asyncio

from src.bench.schema import Paper
from src.core.detector import HallucinationDetector
from src.core.tools import AggregateSearchFactory

# Create a Real sample (no hallucination_type)
real_paper = Paper(
    source="arxiv",
    id="2602.12276",
    title="Agentic Test-Time Scaling for WebAgents",
    abstract="Test-time scaling has become a standard way to improve performance...",
    authors=["Nicholas Lee", "Lutfi Eren Erdogan", "Chris Joseph John"],
    published_date="2026-02-12",
    url="http://arxiv.org/abs/2602.12276v1",
    claims=["CATTS improves performance on WebArena-Lite by 9.1%"],
    hallucination_type=None,  # This is a REAL sample
)

async def test_real_sample():
    print("=" * 80)
    print("Testing REAL sample:")
    print(f"  Title: {real_paper.title}")
    print(f"  Authors: {real_paper.authors}")
    print(f"  Ground Truth: REAL (not hallucinated)")
    print("=" * 80)
    print()

    # Create detector with LOCAL search for faster testing
    print("Using LOCAL database search...")
    search = AggregateSearchFactory.create("local")
    detector = HallucinationDetector(search=search)

    print("Running validation (with verbose output)...")
    print("-" * 80)

    # Patch agent_executor to see intermediate steps
    original_invoke = detector.agent_executor.ainvoke

    async def verbose_invoke(*args, **kwargs):
        result = await original_invoke(*args, **kwargs)
        print("\n--- AGENT RESPONSE ---")
        for i, msg in enumerate(result.get("messages", [])):
            print(f"\n[{i}] {type(msg).__name__}:")
            content = msg.content[:800] if msg.content else "(empty)"
            print(f"  Content: {content}...")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"  Tool calls:")
                for tc in msg.tool_calls:
                    print(f"    - {tc.get('name')}: {tc.get('args', {})}")
        print("\n--- END AGENT RESPONSE ---\n")
        return result

    detector.agent_executor.ainvoke = verbose_invoke

    result = await detector.acheck_reference(real_paper)

    print("=" * 80)
    print("FINAL RESULT:")
    print(f"  is_hallucination: {result.is_hallucination}")
    print(f"  confidence: {result.confidence}")
    print(f"  reasoning: {result.reasoning}")
    print("=" * 80)

    if result.is_hallucination:
        print("\n❌ WRONG: Real paper was classified as HALLUCINATION (False Positive)")
        if "timeout" in result.reasoning.lower():
            print("   CAUSE: Agent timeout - no result from Agent, defaulted to True")
    else:
        print("\n✅ CORRECT: Real paper was classified as REAL")

if __name__ == "__main__":
    asyncio.run(test_real_sample())
