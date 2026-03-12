---
name: valiref
description: AI-powered citation validation for academic papers. Use this skill when the user wants to verify references in PDF documents, check for hallucinated citations, validate academic paper citations, or analyze the authenticity of bibliography entries. Automatically triggers when users mention validating citations, checking references, detecting fake papers, or verifying academic sources.
license: MIT
---

# ValiRef - Citation Validation Skill

## Overview

ValiRef is an AI-powered tool for detecting **hallucinated citations** in academic papers. It validates PDF document references against multiple academic databases to identify:

- **Fabricated papers** - Citations to papers that don't exist
- **Author attribution errors** - Wrong authors listed for real papers
- **Content mismatch** - Paper content doesn't support the cited claim
- **Contradictory conclusions** - Cited paper actually argues the opposite

## When to Use

Use this skill when users:
- Ask to validate citations in a PDF paper
- Want to check if references are real
- Need to verify academic sources
- Suspect hallucinated citations in a document
- Want to check bibliography authenticity
- Need to review reference quality

## Quick Start

### Validate Citations in a PDF

```bash
# Basic validation
valiref validate paper.pdf

# With custom workers
valiref validate paper.pdf --workers 10

# JSON output
valiref validate paper.pdf --json
```

### Python API

```python
from valiref.core.pipeline import ValidationPipeline
from valiref.core.config import settings

# Initialize pipeline
pipeline = ValidationPipeline(
    max_workers=5,
    llm_model="deepseek-chat"
)

# Validate PDF
result = await pipeline.validate_pdf("paper.pdf")

for ref_result in result.references:
    print(f"Reference: {ref_result.title}")
    print(f"Status: {ref_result.status}")
    print(f"Confidence: {ref_result.confidence}")
```

## Installation

### Prerequisites
- Python 3.12+
- DeepSeek API key (for LLM validation)

### Install from PyPI
```bash
pip install valiref
```

### Environment Setup

Create `.env` file:
```bash
DEEPSEEK_API_KEY=your_key_here

# Optional: Enhanced search
SERPAPI_API_KEY=your_key
SEMANTIC_SCHOLAR_API_KEY=your_key
```

## Core Features

### Multi-Source Verification
ValiRef queries multiple academic databases simultaneously:
- **ArXiv** - Preprint server with full-text access
- **Google Scholar** - Broad academic search
- **Semantic Scholar** - AI-powered academic search
- **OpenReview** - Peer-reviewed conference papers
- **OpenAlex** - Open academic graph
- **DuckDuckGo** - Web search fallback

### AI-Powered Detection
Uses DeepSeek LLM with ReAct (Reasoning + Acting) agents to:
- Analyze search results from all sources
- Compare paper metadata (title, authors, abstract, venue)
- Evaluate citation content against actual paper content
- Provide confidence scores with detailed reasoning

### Resilient API Architecture
- **Token bucket rate limiting** - Smooth request flow
- **Circuit breaker pattern** - Auto-stop failed services
- **Graceful degradation** - Failed sources don't block others

## Validation Output

### Example: Real Reference
```
✅ Reference #1 - REAL REFERENCE
Title: Attention Is All You Need
Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, et al.
Confidence: 0.98

Reasoning:
Found exact match on ArXiv (arxiv.org/abs/1706.03762). Title,
authors, and venue (NIPS 2017) all match the citation.

Evidence:
- https://arxiv.org/abs/1706.03762
```

### Example: Hallucinated Reference
```
❌ Reference #5 - FABRICATED PAPER
Title: Quantum Neural Networks for Natural Language Processing
Authors: John Smith, Jane Doe
Confidence: 0.95

Reasoning:
No matching paper found across any source (ArXiv, Google Scholar,
Semantic Scholar, OpenReview). The title and authors do not
appear in any academic database. This appears to be a fabricated
citation.

Evidence:
- ArXiv: No results
- Google Scholar: No results
- Semantic Scholar: No results
```

## Advanced Usage

### Batch Validation
```python
import asyncio
from valiref.core.pipeline import ValidationPipeline

async def validate_multiple(pdf_files):
    pipeline = ValidationPipeline()
    results = await asyncio.gather(*[
        pipeline.validate_pdf(pdf) for pdf in pdf_files
    ])
    return results
```

### Custom Validation Rules
```python
from valiref.core.detector import HallucinationDetector

detector = HallucinationDetector(
    llm_model="deepseek-chat",
    temperature=0.1,  # Lower for more consistent reasoning
    min_confidence=0.8
)
```

### Integration with LangChain
```python
from langchain_deepseek import ChatDeepSeek
from valiref.core.detector import HallucinationDetector

llm = ChatDeepSeek(model="deepseek-chat")
detector = HallucinationDetector(llm=llm)
```

## Benchmark Results

On 100-sample mixed dataset:

| Metric | Value |
|--------|-------|
| **Accuracy** | 72.0% |
| **Precision** | 1.0000 |
| **Recall** | 0.28-1.00 (varies by type) |
| **F1 Score** | 0.44-1.00 (varies by type) |

### By Hallucination Type

| Type | Accuracy | Precision | Recall | F1 |
|------|----------|-----------|--------|-----|
| Fabrication | 100% | 1.00 | 1.00 | 1.00 |
| Attribution Error | 100% | 1.00 | 1.00 | 1.00 |
| Content Mismatch | 74% | 1.00 | 0.74 | 0.85 |
| Contradictory | 28% | 1.00 | 0.28 | 0.44 |
| Real Papers | 72% | 0.00 | 0.00 | 0.00 |

## Configuration

Key settings in `src/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_MODEL` | deepseek-chat | LLM for validation |
| `LLM_TEMPERATURE` | 0.7 | Creativity vs determinism |
| `DETECTOR_TEMPERATURE` | 0.1 | Reasoning consistency |
| `EXTRACTION_CHAR_LIMIT` | 20000 | Max chars from references |
| `MAX_WORKERS` | 5 | Concurrent validation threads |

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  PDF Input  │ →  │   Extract    │ →  │Multi-Source  │ →  │  LLM Verify │
│             │    │  Citations   │    │   Search     │    │             │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
                                                              │
                                                              ▼
                                                        ┌─────────────┐
                                                        │   Report    │
                                                        │             │
                                                        └─────────────┘
```

## Troubleshooting

### API Rate Limits
ValiRef handles rate limiting automatically with:
- Token bucket for smooth request flow
- Exponential backoff for retries
- Circuit breaker for failed services

### Low Confidence Scores
If confidence is below 0.7:
- Check if paper is very recent (may not be indexed)
- Verify citation format is correct
- Consider manual verification for borderline cases

### Missing Papers
If a real paper is not found:
- Try searching with different keywords
- Check if paper is in preprint vs published form
- Some papers may only be in specific databases

## Resources

- **GitHub**: https://github.com/Gianthard-cyh/ValiRef
- **PyPI**: https://pypi.org/project/valiref
- **Documentation**: https://github.com/Gianthard-cyh/ValiRef#readme

## License

MIT License - See LICENSE file for details.
