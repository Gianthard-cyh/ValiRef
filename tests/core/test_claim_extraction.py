"""Tests for TextExtractor claim extraction functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

from src.core.extract import TextExtractor
from src.bench.schema import Paper, Reference


class TestCitationParsing:
    """Test citation pattern recognition."""

    @pytest.fixture
    def extractor(self):
        """Create TextExtractor with mocked LLM."""
        mock_llm = MagicMock()
        extractor = TextExtractor(llm=mock_llm)
        return extractor

    def test_parse_numeric_single(self, extractor):
        """Parse single numeric citation [1]."""
        result = extractor._parse_numeric("[1]")
        assert result == ["1"]

    def test_parse_numeric_multiple(self, extractor):
        """Parse multiple numeric citations [1,2,3]."""
        result = extractor._parse_numeric("[1,2,3]")
        assert result == ["1", "2", "3"]

    def test_parse_numeric_with_spaces(self, extractor):
        """Parse citations with spaces [1, 2, 3]."""
        result = extractor._parse_numeric("[1, 2, 3]")
        assert result == ["1", "2", "3"]

    def test_parse_numeric_range(self, extractor):
        """Parse range citation [1-3]."""
        result = extractor._parse_numeric("[1-3]")
        assert result == ["1", "2", "3"]

    def test_parse_numeric_range_with_spaces(self, extractor):
        """Parse range with spaces [1 - 3]."""
        result = extractor._parse_numeric("[1 - 3]")
        assert result == ["1", "2", "3"]

    def test_parse_numeric_empty(self, extractor):
        """Parse empty citation []."""
        result = extractor._parse_numeric("[]")
        assert result == []

    def test_parse_author_year_simple(self, extractor):
        """Parse simple author-year (Smith, 2024)."""
        result = extractor._parse_author_year("(Smith, 2024)")
        assert result == {'author': 'smith', 'year': '2024'}

    def test_parse_author_year_et_al(self, extractor):
        """Parse author-year with et al. (Smith et al., 2024)."""
        result = extractor._parse_author_year("(Smith et al., 2024)")
        assert result == {'author': 'smith', 'year': '2024'}

    def test_parse_author_year_two_authors(self, extractor):
        """Parse author-year with two authors (Smith and Jones, 2024) - extracts first author."""
        result = extractor._parse_author_year("(Smith and Jones, 2024)")
        assert result == {'author': 'smith', 'year': '2024'}

    def test_parse_author_year_no_match(self, extractor):
        """Parse non-matching citation."""
        result = extractor._parse_author_year("(2024)")
        assert result is None


class TestSentenceSplitting:
    """Test text splitting into sentences."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_split_simple_sentences(self, extractor):
        """Split simple sentences."""
        text = "First sentence. Second sentence. Third sentence."
        sentences = extractor._split_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence."
        assert sentences[2] == "Third sentence."

    def test_split_with_exclamation(self, extractor):
        """Split sentences with exclamation."""
        text = "Wow! This is great. Really."
        sentences = extractor._split_sentences(text)
        assert len(sentences) == 3

    def test_split_with_question(self, extractor):
        """Split sentences with question mark."""
        text = "What is this? It is a test."
        sentences = extractor._split_sentences(text)
        assert len(sentences) == 2

    def test_split_empty(self, extractor):
        """Split empty text."""
        text = ""
        sentences = extractor._split_sentences(text)
        assert sentences == []

    def test_split_multiple_spaces(self, extractor):
        """Split text with multiple spaces."""
        text = "First.   Second."
        sentences = extractor._split_sentences(text)
        assert len(sentences) == 2


class TestClaimBuilding:
    """Test claim context building."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_build_claim_with_previous(self, extractor):
        """Build claim with previous sentence context."""
        sentences = [
            "Previous context here.",
            "Current sentence with citation [1].",
            "Next sentence."
        ]
        claim = extractor._build_claim(1, sentences)
        assert "Previous context here." in claim
        assert "Current sentence with citation [1]." in claim
        assert "Next sentence." not in claim

    def test_build_claim_first_sentence(self, extractor):
        """Build claim for first sentence (no previous)."""
        sentences = [
            "First sentence with citation [1].",
            "Second sentence."
        ]
        claim = extractor._build_claim(0, sentences)
        assert claim == "First sentence with citation [1]."

    def test_build_claim_joins_sentences(self, extractor):
        """Build claim joins sentences with space."""
        sentences = [
            "Previous work has shown promising results in this area.",
            "Current approach builds on these findings with new methods [1]."
        ]
        claim = extractor._build_claim(1, sentences)
        assert claim == "Previous work has shown promising results in this area. Current approach builds on these findings with new methods [1]."


class TestCitationFinding:
    """Test finding citations in sentences."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_find_numeric_citation(self, extractor):
        """Find numeric citation in sentence."""
        sentence = "As shown in [1], the model works well."
        citations = extractor._find_citations(sentence)
        assert len(citations) >= 1
        assert any(c['type'] == 'numeric' for c in citations)

    def test_find_multiple_citations(self, extractor):
        """Find multiple citations in sentence."""
        sentence = "As shown in [1,2] and [3], the model works."
        citations = extractor._find_citations(sentence)
        numeric_cits = [c for c in citations if c['type'] == 'numeric']
        assert len(numeric_cits) >= 2

    def test_find_author_year_citation(self, extractor):
        """Find author-year citation."""
        sentence = "As demonstrated by Smith et al. (2024), the method is effective."
        # Note: author-year pattern may not match if not in parentheses
        sentence2 = "As demonstrated (Smith et al., 2024), the method is effective."
        citations = extractor._find_citations(sentence2)
        author_year_cits = [c for c in citations if c['type'] == 'author_year']
        assert len(author_year_cits) >= 1

    def test_find_no_citation(self, extractor):
        """Find no citations in plain sentence."""
        sentence = "This is a plain sentence without citations."
        citations = extractor._find_citations(sentence)
        assert len(citations) == 0


class TestAuthorNormalization:
    """Test author name normalization."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_normalize_last_name_only(self, extractor):
        """Extract last name from single name."""
        result = extractor._normalize_author("Smith")
        assert result == "smith"

    def test_normalize_first_last(self, extractor):
        """Extract last name from first last."""
        result = extractor._normalize_author("John Smith")
        assert result == "smith"

    def test_normalize_last_first(self, extractor):
        """Extract last name from last, first."""
        result = extractor._normalize_author("Smith, John")
        assert result == "smith"

    def test_normalize_multiple_names(self, extractor):
        """Extract last name from multiple names."""
        result = extractor._normalize_author("John Michael Smith")
        assert result == "smith"

    def test_normalize_empty(self, extractor):
        """Handle empty author."""
        result = extractor._normalize_author("")
        assert result is None


class TestYearExtraction:
    """Test year extraction from dates."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_extract_year_simple(self, extractor):
        """Extract year from simple year."""
        result = extractor._extract_year("2024")
        assert result == "2024"

    def test_extract_year_from_date(self, extractor):
        """Extract year from date string."""
        result = extractor._extract_year("January 15, 2024")
        assert result == "2024"

    def test_extract_year_from_range(self, extractor):
        """Extract year from year range."""
        result = extractor._extract_year("2023-2024")
        assert result == "2023"

    def test_extract_year_no_year(self, extractor):
        """Handle no year in string."""
        result = extractor._extract_year("No year here")
        assert result is None


class TestClaimAssociation:
    """Test associating claims to papers."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    @pytest.fixture
    def sample_papers(self):
        """Create sample papers for testing."""
        return [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, John"],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
            Paper(
                source="ref",
                id="2",
                title="Paper Two",
                abstract="N/A",
                authors=["Jones, Bob"],
                published_date="2023",
                url="N/A",
                venue="ICML",
                claims=[]
            ),
        ]

    def test_associate_numeric_single(self, extractor, sample_papers):
        """Associate claim to single paper by numeric citation."""
        # Only main text (before References), no References section
        main_text = """Introduction
        As shown in [1], the method works well."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 1
        assert "As shown in [1]" in papers[0].claims[0]
        assert len(papers[1].claims) == 0

    def test_associate_numeric_multiple(self, extractor, sample_papers):
        """Associate claim to multiple papers."""
        main_text = """Method
        Previous work [1,2] has shown promising results."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 1
        assert len(papers[1].claims) == 1

    def test_associate_numeric_range(self, extractor, sample_papers):
        """Associate claim using range citation [1-2]."""
        main_text = """Results
        As discussed in [1-2], both methods work."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 1
        assert len(papers[1].claims) == 1

    def test_associate_author_year(self, extractor, sample_papers):
        """Associate claim using author-year citation."""
        main_text = """Method
        Recent work (Smith, 2024) demonstrates this."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 1
        assert "Recent work (Smith, 2024)" in papers[0].claims[0]

    def test_claim_includes_previous_sentence(self, extractor, sample_papers):
        """Claim includes context from previous sentence."""
        main_text = """Introduction
        The problem is challenging. As shown in [1], the solution works."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert "The problem is challenging." in papers[0].claims[0]
        assert "As shown in [1]" in papers[0].claims[0]

    def test_no_claim_for_uncited_paper(self, extractor, sample_papers):
        """Paper with no citations gets no claims."""
        main_text = """Introduction
        Only [1] is cited here."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 1
        assert len(papers[1].claims) == 0


class TestAuthorValidation:
    """Test author format validation and normalization."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_accept_correct_format(self, extractor):
        """Accept correct 'LastName, FirstName' format."""
        authors = ["Smith, John", "Jones, Bob"]
        result = extractor._normalize_authors(authors, 1, "Test Paper")
        assert result == authors

    def test_normalize_first_last_format(self, extractor):
        """Normalize 'FirstName LastName' to 'LastName, FirstName'."""
        authors = ["John Smith"]
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        assert result == ["Smith, John"]

    def test_detect_academic_title(self, extractor):
        """Detect and warn about academic titles - keeps original."""
        authors = ["Dr. Smith, John"]
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        assert result == ["Dr. Smith, John"]  # Kept as-is but warned

    def test_detect_professor_title(self, extractor):
        """Detect 'Prof.' title - keeps original."""
        authors = ["Prof. Jones, Bob"]
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        assert "Prof. Jones, Bob" in result

    def test_accept_institution_name(self, extractor):
        """Accept institution names without comma."""
        # OpenAI (mixed case, single word) and 3+ word institution
        authors = ["OpenAI", "Google DeepMind Research"]
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        assert result[0] == "OpenAI"  # Mixed case single word, kept
        assert result[1] == "Google DeepMind Research"  # 3 words, kept

    def test_normalize_with_middle_initial(self, extractor):
        """Normalize name with middle initial (has punctuation)."""
        authors = ["John A. Smith"]
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        # Has punctuation (A.), so normalized
        assert result == ["Smith, John A."]

    def test_skip_n_and_empty(self, extractor):
        """Skip 'N/A' and empty strings."""
        authors = ["Smith, John", "N/A", ""]
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        assert result == ["Smith, John"]

    def test_keep_original_if_cannot_normalize(self, extractor):
        """Keep original if cannot normalize (single word)."""
        authors = ["Smith"]  # Single word, can't determine first/last
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        assert result == ["Smith"]

    def test_normalize_multi_word_name(self, extractor):
        """Normalize multi-word first name."""
        authors = ["Mary Ann Smith"]  # 3 words, no punctuation
        result = extractor._normalize_authors(authors, 1, "Test Paper")

        # 3 words, treated as institution, so kept as-is
        assert result == ["Mary Ann Smith"]


class TestTextPreprocessing:
    """Test text preprocessing for fixing broken citations."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_fix_bracket_newline_number(self, extractor):
        """Fix [\n 1] pattern."""
        text = "As shown in [\n1], the method works."
        result = extractor._preprocess_text(text)
        assert "[1]" in result
        assert "[\n1]" not in result

    def test_fix_number_newline_bracket(self, extractor):
        """Fix [1\n ] pattern."""
        text = "As shown in [1\n], the method works."
        result = extractor._preprocess_text(text)
        assert "[1]" in result
        assert "[1\n]" not in result

    def test_fix_comma_after_newline(self, extractor):
        """Fix [1,\n 2] pattern."""
        text = "Previous work [1,\n2] has shown."
        result = extractor._preprocess_text(text)
        assert "[1, 2]" in result
        assert "[1,\n2]" not in result

    def test_fix_newline_before_comma(self, extractor):
        """Fix [1\n, 2] pattern."""
        text = "Previous work [1\n, 2] has shown."
        result = extractor._preprocess_text(text)
        assert "[1, 2]" in result
        assert "[1\n, 2]" not in result

    def test_fix_range_with_newline(self, extractor):
        """Fix [1-\n 3] pattern."""
        text = "As discussed in [1-\n3], both methods work."
        result = extractor._preprocess_text(text)
        assert "[1-3]" in result
        assert "[1-\n3]" not in result

    def test_fix_multiline_citation(self, extractor):
        """Fix citation with brackets on separate lines."""
        text = """As shown in [
        1, 2, 3
        ], the methods work."""
        result = extractor._preprocess_text(text)
        assert "[1, 2, 3]" in result

    def test_no_change_for_normal_citation(self, extractor):
        """Normal citations should not be affected."""
        text = "As shown in [1], the method works."
        result = extractor._preprocess_text(text)
        assert result == text

    def test_no_change_for_multiple_citations(self, extractor):
        """Multiple normal citations should not be affected."""
        text = "Previous work [1, 2, 3] has shown promising results."
        result = extractor._preprocess_text(text)
        assert result == text

    def test_complex_multiline_citation(self, extractor):
        """Handle complex multiline citation."""
        text = """We build upon [
        1,
        2,
        3
        ] for our method."""
        result = extractor._preprocess_text(text)
        assert "[1, 2, 3]" in result

    def test_multiline_citation_many_numbers(self, extractor):
        """Handle multiline citation with many numbers [1,2,3,4,5]."""
        text = """Previous work [
        1,
        2,
        3,
        4,
        5
        ] has shown."""
        result = extractor._preprocess_text(text)
        assert "[1, 2, 3, 4, 5]" in result

    def test_multiline_citation_many_numbers_inline(self, extractor):
        """Handle multiline citation with many numbers inline."""
        text = "Previous work [1,\n2,\n3,\n4,\n5] has shown."
        result = extractor._preprocess_text(text)
        assert "[1, 2, 3, 4, 5]" in result
        assert "[1,\\n2" not in result


class TestAuthorNameHandling:
    """Test author name extraction and matching edge cases."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_normalize_initialed_author(self, extractor):
        """Handle author with initials: Smith, J."""
        result = extractor._normalize_author("Smith, J.")
        assert result == "smith"

    def test_normalize_initialed_first(self, extractor):
        """Handle author with initials first: J. Smith"""
        result = extractor._normalize_author("J. Smith")
        assert result == "smith"

    def test_normalize_hyphenated_last_name(self, extractor):
        """Handle hyphenated surname: Smith-Jones"""
        result = extractor._normalize_author("Smith-Jones, John")
        assert result == "smith-jones"

    def test_normalize_apostrophe_name(self, extractor):
        """Handle apostrophe in name: O'Connor"""
        result = extractor._normalize_author("O'Connor, Mary")
        assert result == "o'connor"

    def test_normalize_eastern_name_comma(self, extractor):
        """Handle Eastern name order with comma: Li, Wei"""
        result = extractor._normalize_author("Li, Wei")
        assert result == "li"

    def test_normalize_eastern_name_space(self, extractor):
        """Handle Eastern name order without comma: Wei Li"""
        result = extractor._normalize_author("Wei Li")
        assert result == "li"

    def test_normalize_von_prefix(self, extractor):
        """Handle von/de/van prefix: von Neumann, John"""
        result = extractor._normalize_author("von Neumann, John")
        assert result == "von neumann"

    def test_normalize_de_la_prefix(self, extractor):
        """Handle de la prefix: de la Cruz, Maria"""
        result = extractor._normalize_author("de la Cruz, Maria")
        assert result == "de la cruz"

    def test_normalize_institution_author(self, extractor):
        """Handle institution name: OpenAI"""
        result = extractor._normalize_author("OpenAI")
        assert result == "openai"

    def test_normalize_institution_multiword(self, extractor):
        """Handle multi-word institution: Google Research"""
        result = extractor._normalize_author("Google Research")
        assert result == "research"


class TestAuthorYearMatchingEdgeCases:
    """Test author-year citation matching edge cases."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_match_initialed_author(self, extractor):
        """Match (Smith, 2024) to 'Smith, J.' in references."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, J."],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
        ]
        # Should match despite initials
        main_text = "Recent work (Smith, 2024) shows this."
        papers = extractor._extract_claims(main_text, papers)
        assert len(papers[0].claims) == 1

    def test_match_hyphenated_author(self, extractor):
        """Match (Smith-Jones, 2024) to hyphenated name."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith-Jones, Ann"],
                published_date="2024",
                url="N/A",
                venue="ICML",
                claims=[]
            ),
        ]
        main_text = "As shown in (Smith-Jones, 2024)."
        papers = extractor._extract_claims(main_text, papers)
        assert len(papers[0].claims) == 1

    def test_match_de_la_prefix_author(self, extractor):
        """Match (de la Cruz, 2024) to 'de la Cruz, Maria'."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["de la Cruz, Maria"],
                published_date="2024",
                url="N/A",
                venue="ACL",
                claims=[]
            ),
        ]
        main_text = "Following the approach of (de la Cruz, 2024), we improve the model significantly."
        papers = extractor._extract_claims(main_text, papers)
        assert len(papers[0].claims) == 1

    def test_match_institution_author(self, extractor):
        """Match (OpenAI, 2024) to institution name."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="GPT-5 Technical Report",
                abstract="N/A",
                authors=["OpenAI"],
                published_date="2024",
                url="N/A",
                venue="arXiv",
                claims=[]
            ),
        ]
        main_text = "According to (OpenAI, 2024), models improve."
        papers = extractor._extract_claims(main_text, papers)
        assert len(papers[0].claims) == 1

    def test_ambiguous_surname_multiple_authors(self, extractor):
        """Handle same surname, different first names."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, John"],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
            Paper(
                source="ref",
                id="2",
                title="Paper Two",
                abstract="N/A",
                authors=["Smith, Jane"],
                published_date="2024",
                url="N/A",
                venue="ICML",
                claims=[]
            ),
        ]
        # (Smith, 2024) is ambiguous - should match both
        main_text = "As shown in (Smith, 2024), both methods achieve similar performance."
        papers = extractor._extract_claims(main_text, papers)
        # Both papers should get the claim
        assert len(papers[0].claims) == 1
        assert len(papers[1].claims) == 1

    def test_author_year_with_et_al(self, extractor):
        """Handle (Smith et al., 2024) citation."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, John", "Jones, Bob", "Lee, Ann"],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
        ]
        main_text = "Smith et al., 2024) proposed this."
        papers = extractor._extract_claims(main_text, papers)
        assert len(papers[0].claims) == 0  # Missing opening parenthesis won't match

        main_text2 = "Recent work (Smith et al., 2024) proposed this."
        papers2 = extractor._extract_claims(main_text2, papers)
        assert len(papers2[0].claims) == 1

    def test_author_year_lowercase_in_citation(self, extractor):
        """Handle (smith, 2024) lowercase in citation - should match case-insensitively."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, John"],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
        ]
        # Now matches case-insensitively
        main_text = "As shown in (smith, 2024), the approach works well on benchmarks."
        papers = extractor._extract_claims(main_text, papers)
        # Should match despite lowercase
        assert len(papers[0].claims) == 1

    def test_author_year_with_multiple_authors_in_parens(self, extractor):
        """Handle (Smith and Jones, 2024) multiple authors in citation."""
        papers = [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, John", "Jones, Bob"],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
        ]
        main_text = "Recent work (Smith and Jones, 2024) shows this."
        papers = extractor._extract_claims(main_text, papers)
        assert len(papers[0].claims) == 1


class TestDocumentSplitting:
    """Test document splitting into main text and References section."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_split_with_references_header(self, extractor):
        """Split document with References header."""
        # Make text long enough to trigger search from middle
        text = """Introduction section with enough content to make the document long.
        This is the intro with more text.
        {" " * 500}
        References
        [1] Smith et al., Paper One.
        [2] Jones et al., Paper Two."""

        main_text, ref_section = extractor._split_document(text)

        assert "Introduction" in main_text
        assert "References" not in main_text
        assert "[1] Smith" in ref_section
        assert "[2] Jones" in ref_section

    def test_split_with_bibliography_header(self, extractor):
        """Split document with Bibliography header."""
        text = """Method section with content.
        {" " * 500}
        Bibliography
        [1] Smith et al."""

        main_text, ref_section = extractor._split_document(text)

        assert "Method" in main_text
        assert "Bibliography" in ref_section
        assert "[1] Smith" in ref_section

    def test_split_uppercase_references(self, extractor):
        """Split document with uppercase REFERENCES header."""
        text = """Results section with content.
        {" " * 500}
        REFERENCES
        [1] Smith et al."""

        main_text, ref_section = extractor._split_document(text)

        assert "Results" in main_text
        assert "REFERENCES" in ref_section
        assert "[1] Smith" in ref_section

    def test_split_no_references_found(self, extractor):
        """Fallback when no References section found."""
        text = ("Just some text without any references section. " * 1000)  # Make it long enough (>20000 chars)

        main_text, ref_section = extractor._split_document(text)

        # Should split at EXTRACTION_CHAR_LIMIT from end
        assert len(main_text) > 0
        assert len(ref_section) > 0

    def test_split_references_in_middle_ignored(self, extractor):
        """References in middle of text (like Table of Contents) should be ignored."""
        text = """Table of Contents
        References ... page 5

        Introduction
        This is the actual content.

        References
        [1] Smith et al., Real Reference."""

        main_text, ref_section = extractor._split_document(text)

        # Should find the last References section
        assert "Table of Contents" in main_text
        assert "Real Reference" in ref_section
        assert "page 5" not in ref_section
    """Test edge cases and error handling."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    @pytest.fixture
    def sample_papers(self):
        """Create sample papers for testing."""
        return [
            Paper(
                source="ref",
                id="1",
                title="Paper One",
                abstract="N/A",
                authors=["Smith, John"],
                published_date="2024",
                url="N/A",
                venue="NeurIPS",
                claims=[]
            ),
            Paper(
                source="ref",
                id="2",
                title="Paper Two",
                abstract="N/A",
                authors=["Jones, Bob"],
                published_date="2023",
                url="N/A",
                venue="ICML",
                claims=[]
            ),
        ]

    def test_citation_in_parentheses_not_author_year(self, extractor):
        """Handle parenthetical text that's not citation."""
        text = "This is (not a citation) just text."
        citations = extractor._find_citations(text)
        # Should not match author-year pattern without author
        author_year = [c for c in citations if c['type'] == 'author_year']
        assert len(author_year) == 0

    def test_citation_at_sentence_start(self, extractor, sample_papers):
        """Handle citation at start of sentence (no previous context)."""
        main_text = """Introduction. [1] demonstrates this approach."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 1
        # Should include previous sentence context (Introduction.)
        assert "[1] demonstrates" in papers[0].claims[0]

    def test_duplicate_citations_same_paper(self, extractor, sample_papers):
        """Paper cited multiple times gets multiple claims."""
        main_text = """Introduction provides background information.
        First mention of this important work is in [1].
        Later we see [1] again in the discussion section."""

        papers = extractor._extract_claims(main_text, sample_papers)

        assert len(papers[0].claims) == 2

    def test_citation_in_equation(self, extractor):
        """Handle citation in mathematical context."""
        # Equations might have brackets that look like citations
        text = "The formula is f(x) = x^2 [1] for all x."
        # This should still match [1] as a citation
        citations = extractor._find_citations(text)
        numeric = [c for c in citations if c['type'] == 'numeric']
        assert len(numeric) >= 1


class TestSectionHeaderFiltering:
    """Test filtering of section headers from claims."""

    @pytest.fixture
    def extractor(self):
        mock_llm = MagicMock()
        return TextExtractor(llm=mock_llm)

    def test_filter_section_header_numbered(self, extractor):
        """Filter section headers like '2 RELATED WORK'."""
        sentences = [
            "Previous work is important.",
            "2 RELATED WORK",
            "This paper proposes a new method [1]."
        ]
        claim = extractor._build_claim(2, sentences)
        assert claim is not None
        assert "2 RELATED WORK" not in claim

    def test_filter_section_header_subsection(self, extractor):
        """Filter subsection headers like '3.1 Method'."""
        sentences = [
            "Introduction to methods and related work.",
            "3.1 EXPERIMENTAL SETUP",
            "Results show significant improvement in our experiments [1]."
        ]
        claim = extractor._build_claim(2, sentences)
        assert claim is not None
        assert "3.1" not in claim

    def test_filter_table_caption(self, extractor):
        """Filter table captions."""
        sentences = [
            "Table 1 shows the results.",
            "The method outperforms baseline [1]."
        ]
        claim = extractor._build_claim(1, sentences)
        assert claim is not None
        assert "Table 1" not in claim

    def test_filter_figure_caption(self, extractor):
        """Filter figure captions."""
        sentences = [
            "Figure 2 illustrates the architecture.",
            "This design enables better performance [1]."
        ]
        claim = extractor._build_claim(1, sentences)
        assert claim is not None
        assert "Figure 2" not in claim

    def test_filter_short_sentence(self, extractor):
        """Filter very short sentences."""
        sentences = [
            "Ok.",
            "This is a complete sentence with citation [1]."
        ]
        claim = extractor._build_claim(1, sentences)
        assert claim is not None
        assert "Ok." not in claim

    def test_section_header_returns_none(self, extractor):
        """Section header sentence returns None."""
        sentences = ["2 RELATED WORK"]
        claim = extractor._build_claim(0, sentences)
        assert claim is None

    def test_is_header_patterns(self, extractor):
        """Test various section header patterns."""
        assert extractor._is_header("2 RELATED WORK") is True
        assert extractor._is_header("3.1 Method") is True
        assert extractor._is_header("REFERENCES") is True
        assert extractor._is_header("Table 1") is True
        assert extractor._is_header("Fig. 2") is True
        assert extractor._is_header("This is a normal claim.") is False
        assert extractor._is_header("The model achieves 95% accuracy.") is False
