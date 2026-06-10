"""
Unit tests for BibTeXExtractor.
"""

import pytest
from pathlib import Path

from src.core.extract import BibTeXExtractor
from src.core.exceptions import ExtractionError, ErrorCode
from src.bench.schema import Paper


class TestBibTeXExtractor:
    """Tests for BibTeXExtractor."""

    @pytest.fixture
    def extractor(self):
        return BibTeXExtractor()

    @pytest.fixture
    def valid_bib_file(self, tmp_path):
        bib_content = """
@article{smith2023example,
    title={An Example Paper for Testing},
    author={Smith, John and Doe, Jane},
    journal={Journal of Examples},
    year={2023},
    volume={10},
    pages={1--10},
    doi={10.1000/example}
}

@inproceedings{lee2024conference,
    title={A Conference Paper},
    author={Lee, Bob and Wang, Alice},
    booktitle={Proc. of Example Conference},
    year={2024},
    url={https://example.com/paper}
}
"""
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(bib_content, encoding="utf-8")
        return str(bib_file)

    @pytest.fixture
    def bib_with_arxiv(self, tmp_path):
        bib_content = """
@article{arxiv2023,
    title={ArXiv Paper Title},
    author={Author, One},
    journal={arXiv preprint},
    year={2023},
    eprint={2301.12345},
    archivePrefix={arXiv}
}
"""
        bib_file = tmp_path / "arxiv.bib"
        bib_file.write_text(bib_content, encoding="utf-8")
        return str(bib_file)

    @pytest.fixture
    def bib_no_titles(self, tmp_path):
        bib_content = """
@article{notitle1,
    author={Smith, John},
    year={2023}
}

@article{notitle2,
    author={Doe, Jane},
    year={2024}
}
"""
        bib_file = tmp_path / "no_titles.bib"
        bib_file.write_text(bib_content, encoding="utf-8")
        return str(bib_file)

    @pytest.fixture
    def bib_partial_titles(self, tmp_path):
        bib_content = """
@article{hastitle,
    title={Valid Paper},
    author={Smith, John},
    year={2023}
}

@article{notitle,
    author={Doe, Jane},
    year={2024}
}
"""
        bib_file = tmp_path / "partial.bib"
        bib_file.write_text(bib_content, encoding="utf-8")
        return str(bib_file)

    @pytest.fixture
    def invalid_bib_file(self, tmp_path):
        """A file with binary content that cannot be parsed as BibTeX."""
        bib_file = tmp_path / "invalid.bib"
        bib_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe")
        return str(bib_file)

    @pytest.mark.asyncio
    async def test_extract_valid_bibtex(self, extractor, valid_bib_file):
        """Test extracting from a valid BibTeX file."""
        papers = await extractor.extract(valid_bib_file)

        assert len(papers) == 2

        # First paper
        paper1 = papers[0]
        assert isinstance(paper1, Paper)
        assert paper1.title == "An Example Paper for Testing"
        assert paper1.authors == ["Smith, John", "Doe, Jane"]
        assert paper1.published_date == "2023"
        assert paper1.venue == "Journal of Examples"
        assert paper1.url == "10.1000/example"
        assert paper1.source == "bibtex"

        # Second paper
        paper2 = papers[1]
        assert paper2.title == "A Conference Paper"
        assert paper2.authors == ["Lee, Bob", "Wang, Alice"]
        assert paper2.published_date == "2024"
        assert paper2.venue == "Proc. of Example Conference"
        assert paper2.url == "https://example.com/paper"

    @pytest.mark.asyncio
    async def test_extract_bibtex_arxiv_id(self, extractor, bib_with_arxiv):
        """Test that arXiv eprint is mapped to paper id."""
        papers = await extractor.extract(bib_with_arxiv)

        assert len(papers) == 1
        assert papers[0].id == "2301.12345"
        assert papers[0].title == "ArXiv Paper Title"

    @pytest.mark.asyncio
    async def test_extract_bibtex_no_title_skipped(self, extractor, bib_partial_titles):
        """Test that entries without titles are skipped."""
        papers = await extractor.extract(bib_partial_titles)

        assert len(papers) == 1
        assert papers[0].title == "Valid Paper"

    @pytest.mark.asyncio
    async def test_extract_bibtex_all_no_titles_raises(self, extractor, bib_no_titles):
        """Test that all entries without titles raises ExtractionError."""
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract(bib_no_titles)

        assert exc_info.value.error_code == ErrorCode.NO_REFERENCES_FOUND
        assert "No valid references" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_extract_bibtex_parse_error_raises(self, extractor, invalid_bib_file):
        """Test that invalid BibTeX raises ExtractionError."""
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract(invalid_bib_file)

        assert exc_info.value.error_code == ErrorCode.EXTRACTION_FAILED

    @pytest.mark.asyncio
    async def test_extract_progress_callback(self, extractor, valid_bib_file):
        """Test that on_progress is called for each entry."""
        progress_calls = []

        def on_progress(count, new_refs):
            progress_calls.append((count, len(new_refs)))

        papers = await extractor.extract(valid_bib_file, on_progress=on_progress)

        assert len(papers) == 2
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 1)
        assert progress_calls[1] == (2, 1)

    @pytest.mark.asyncio
    async def test_extract_batch(self, extractor, valid_bib_file, bib_with_arxiv):
        """Test extract_batch with multiple files."""
        results = await extractor.extract_batch([valid_bib_file, bib_with_arxiv])

        assert len(results) == 2
        assert len(results[0]) == 2
        assert len(results[1]) == 1

    @pytest.mark.asyncio
    async def test_extract_missing_fields_defaults(self, extractor, tmp_path):
        """Test that missing fields use default values."""
        bib_content = """
@article{minimal,
    title={Minimal Entry},
    author={Author, Only}
}
"""
        bib_file = tmp_path / "minimal.bib"
        bib_file.write_text(bib_content, encoding="utf-8")

        papers = await extractor.extract(str(bib_file))

        assert len(papers) == 1
        paper = papers[0]
        assert paper.title == "Minimal Entry"
        assert paper.authors == ["Author, Only"]
        assert paper.published_date == "N/A"
        assert paper.url == "N/A"
        assert paper.abstract == "N/A"
        assert paper.venue is None
        assert paper.id == "N/A"
