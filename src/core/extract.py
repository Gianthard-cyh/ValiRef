from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Dict, Tuple, Match, Set
import re
import fitz  # pymupdf
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate

from ..bench.schema import Paper, ReferenceList, Reference
from .config import (
    DEEPSEEK_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    LLM_MAX_RETRIES,
    EXTRACTION_CHAR_LIMIT,
)
from .exceptions import ExtractionError, ErrorCode
from .logger import logger

"""
Extract structured information from the input
"""


class Extractor(ABC):
    """
    Abstract base class for extractors
    """

    @abstractmethod
    async def extract(self, *args) -> List[Paper]:
        """
        Extract a list of referenced papers from the input
        """
        raise NotImplementedError

    @abstractmethod
    async def extract_batch(self, *args) -> List[List[Paper]]:
        """
        Extract lists of referenced papers from a batch of inputs
        """
        raise NotImplementedError


class TextExtractor(Extractor):
    """Extract references and their associated claims from text."""

    # Regex patterns for citation detection - precompiled for performance
    _CITATION_PATTERNS = [
        (re.compile(r'\[(\d+(?:\s*,\s*\d+)*)\]'), 'numeric'),
        (re.compile(r'\[(\d+\s*-\s*\d+)\]'), 'numeric_range'),
        (re.compile(r'\(([^,]+?\s*,\s*\d{4})\)'), 'author_year'),
    ]

    # Section header detection patterns - precompiled
    _HEADER_NUMBERED = re.compile(r'^\d+(?:\.\d+)?\s+[A-Z]')
    _HEADER_ALL_CAPS = re.compile(r'^[A-Z][A-Z\s\d\-]+$')
    _FIGURE_TABLE = re.compile(r'^(?:Table|Figure|Fig\.)\s*\d', re.IGNORECASE)
    _CITATION_BRACKETS = re.compile(r'\[.*?\]')

    # Preprocessing patterns
    _PREPROCESS_PATTERNS = [
        (re.compile(r'\[\s*\n\s*(\d+)'), r'[\1'),           # [\n 1] -> [1]
        (re.compile(r'(\d+)\s*\n\s*\]'), r'\1]'),           # [1\n ] -> [1]
        (re.compile(r'(\d+)\s*,\s*\n\s*(\d+)'), r'\1, \2'),  # [1,\n 2] -> [1, 2]
        (re.compile(r'(\d+)\s*\n\s*,'), r'\1,'),             # [1\n, 2] -> [1, 2]
        (re.compile(r'(\d+)\s*-\s*\n\s*(\d+)'), r'\1-\2'),   # [1-\n 3] -> [1-3]
        (re.compile(r'\[\s*\n\s*((?:\d+\s*,?\s*)+)\n\s*\]'), r'[\1]'),  # [\n 1, 2, 3 \n] -> [1, 2, 3]
    ]
    _MULTILINE_CITATION = re.compile(r'\[(\d[^\]]*?)\]')

    # Sentence splitting
    _SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

    def __init__(self, llm: Optional[ChatDeepSeek] = None):
        if llm is not None:
            self.model = llm
        else:
            if DEEPSEEK_API_KEY is None:
                raise ValueError("DEEPSEEK_API_KEY is not set")

            self.model = ChatDeepSeek(
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                timeout=LLM_TIMEOUT,
                max_retries=LLM_MAX_RETRIES,
                api_key=DEEPSEEK_API_KEY,
            )

    async def extract(
        self,
        text: str,
        on_progress: Optional[Callable[[int, List[Reference]], None]] = None,
    ) -> List[Paper]:
        """
        Extract references and their claims from text.
        Phase 1: Extract references from References section
        Phase 2: Scan main text (before References) for claims
        """
        self._validate_input(text)

        # Preprocess: fix line breaks in citations
        text = self._preprocess_text(text)

        # Split document: body vs references
        body, refs = self._split_document(text)

        # Phase 1: Extract references from References section
        papers = await self._extract_refs(refs, on_progress)
        if not papers:
            return []

        # Phase 2: Extract and associate claims from body only
        papers = self._extract_claims(body, papers)

        return papers

    def _preprocess_text(self, text: str) -> str:
        """Fix common PDF extraction issues with citations split across lines."""
        # Apply preprocessing patterns
        for pattern, replacement in self._PREPROCESS_PATTERNS:
            text = pattern.sub(replacement, text)

        # Remove newlines within citation brackets
        def fix_citation(match):
            return f'[{re.sub(r"\s+", " ", match.group(1))}]'

        return self._MULTILINE_CITATION.sub(fix_citation, text)

    def _split_document(self, text: str) -> Tuple[str, str]:
        """Split document into body and references section."""
        headers = ["References", "Bibliography", "REFERENCES", "BIBLIOGRAPHY"]
        ref_pos = -1

        for header in headers:
            # Search from middle to end to find the actual References section
            search_start = len(text) // 2
            pos = text.rfind(header, search_start)
            if pos != -1 and pos > ref_pos:
                ref_pos = pos

        if ref_pos == -1:
            # No References section found - treat all as references (fallback)
            if len(text) <= EXTRACTION_CHAR_LIMIT:
                return "", text
            return text[:-EXTRACTION_CHAR_LIMIT], text[-EXTRACTION_CHAR_LIMIT:]

        # Split at References header
        return text[:ref_pos].strip(), text[ref_pos:ref_pos + EXTRACTION_CHAR_LIMIT]

    def _validate_input(self, text: str) -> None:
        """Validate input text meets minimum requirements."""
        if not text or not text.strip():
            raise ExtractionError(
                message="PDF contains no text content (possibly a scanned image PDF)",
                error_code=ErrorCode.PDF_NO_TEXT,
            )

        stripped = text.strip()
        if len(stripped) < 500:
            raise ExtractionError(
                message=f"PDF text too short ({len(stripped)} chars), cannot extract references",
                error_code=ErrorCode.PDF_TOO_SHORT,
            )

    async def _extract_refs(self, refs: str, on_progress=None) -> List[Paper]:
        """Extract reference list from References section."""
        prompt = ChatPromptTemplate.from_template(
            "You are an expert researcher. Extract a list of referenced/cited research papers from the following text segment.\n"
            "The text is the END of a research paper, containing the References/Bibliography section.\n"
            "Extract as many references as possible into the ReferenceList schema.\n"
            "\n"
            "CRITICAL - Author Format Rules:\n"
            "- For each author, use format 'LastName, FirstName' (e.g., 'Smith, John')\n"
            "- Do NOT use 'FirstName LastName' format\n"
            "- Do NOT include titles like 'Dr.' or 'Prof.'\n"
            "- For institutions like 'OpenAI', use as-is\n"
            "- For names with particles like 'de la Cruz', include the full particle\n"
            "\n"
            "Fields to extract:\n"
            "- Title: Paper title\n"
            "- Authors: List of authors in 'LastName, FirstName' format\n"
            "- Date: Publication year\n"
            "- ArXiv ID: If present (e.g., '2401.12345')\n"
            "- Venue: Conference or journal name (e.g., 'NeurIPS', 'ICLR', 'Nature')\n"
            "\n"
            "If a field is missing, use 'N/A'.\n"
            "\n"
            "Text Segment:\n{text}"
        )

        structured_llm = self.model.with_structured_output(ReferenceList)
        chain = prompt | structured_llm

        if on_progress:
            result = await self._extract_with_progress(chain, refs, on_progress)
        else:
            result = await chain.ainvoke({"text": refs})

        if result is None or not result.references:
            raise ExtractionError(
                message="No references found in the PDF.",
                error_code=ErrorCode.NO_REFERENCES_FOUND,
            )

        return self._convert_to_papers(result.references)

    async def _extract_with_progress(
        self,
        chain,
        text: str,
        on_progress: Callable[[int, List[Reference]], None],
    ) -> Optional[ReferenceList]:
        """Extract references with progress streaming."""
        last_count = 0
        result: Optional[ReferenceList] = None

        async for partial in chain.astream({"text": text}):
            result = partial
            if partial.references and len(partial.references) > last_count:
                new_count = len(partial.references)
                new_refs = partial.references[last_count:new_count]
                on_progress(new_count, new_refs)
                last_count = new_count

        return result

    def _convert_to_papers(self, references: List[Reference]) -> List[Paper]:
        """Convert Reference objects to Paper objects with validation."""
        papers = []
        for idx, ref in enumerate(references, start=1):
            # Validate author format
            validated_authors = self._normalize_authors(ref.authors, idx, ref.title)

            paper = Paper(
                source="reference",
                id=ref.arxiv_id if ref.arxiv_id else f"ref_{idx}",
                title=ref.title,
                abstract="N/A",
                authors=validated_authors,
                published_date=ref.date,
                url=f"https://arxiv.org/abs/{ref.arxiv_id}" if ref.arxiv_id else "N/A",
                pdf_url=f"https://arxiv.org/pdf/{ref.arxiv_id}.pdf" if ref.arxiv_id else None,
                venue=ref.venue,
                claims=[],  # Will be populated in Phase 2
            )
            papers.append(paper)
        return papers

    def _normalize_authors(self, authors: List[str], idx: int, title: str) -> List[str]:
        """Validate author format and normalize if possible."""
        validated = []
        titles = {'dr.', 'prof.', 'professor', 'mr.', 'mrs.', 'ms.'}

        for author in authors:
            author = author.strip()
            if not author or author.lower() == 'n/a':
                continue

            lower = author.lower()
            has_title = any(lower.startswith(t) or f' {t} ' in lower or lower.endswith(t) for t in titles)
            if has_title:
                logger.warning(
                    "Author contains academic title",
                    reference_index=idx,
                    title=title[:50],
                    author=author,
                    expected_format="LastName, FirstName (no titles)",
                )

            has_comma = ',' in author
            has_punct = any(c in author for c in '.')
            words = [w for w in author.split() if w]

            has_mixed = any(
                w[0].isupper() and any(c.islower() for c in w[1:])
                for w in words
            ) if words else False

            is_institution = (
                len(words) >= 3 or
                (len(words) == 1 and len(words[0]) > 4 and has_mixed)
            ) and not has_punct

            if not has_comma and not is_institution:
                logger.warning(
                    "Author format may be incorrect",
                    reference_index=idx,
                    title=title[:50],
                    author=author,
                    expected_format="LastName, FirstName (e.g., 'Smith, John')",
                )
                parts = author.split()
                if len(parts) >= 2:
                    normalized = f"{parts[-1]}, {' '.join(parts[:-1])}"
                    logger.info(
                        "Normalized author format",
                        reference_index=idx,
                        original=author,
                        normalized=normalized,
                    )
                    validated.append(normalized)
                else:
                    validated.append(author)
            else:
                validated.append(author)

        return validated if validated else authors

    def _extract_claims(
        self,
        text: str,
        papers: List[Paper],
    ) -> List[Paper]:
        """Extract claims from full text and associate with papers."""
        # Build index: numeric citation -> paper
        index = {str(i + 1): paper for i, paper in enumerate(papers)}

        # Build index: (author, year) -> papers (for author-year citations)
        author_index: Dict[Tuple[str, str], List[Paper]] = {}
        for paper in papers:
            year = self._extract_year(paper.published_date)
            if year and paper.authors:
                first = self._normalize_author(paper.authors[0])
                if first:
                    key = (first, year)
                    if key not in author_index:
                        author_index[key] = []
                    author_index[key].append(paper)

        # Split text into sentences for context extraction
        sentences = self._split_sentences(text)

        # Scan for citations
        for i, sentence in enumerate(sentences):
            citations = self._find_citations(sentence)
            if not citations:
                continue

            # Build claim with context
            claim = self._build_claim(i, sentences)
            if claim is None:
                continue

            # Associate with papers
            self._associate_claims(
                citations, claim, index, author_index
            )

        return papers

    def _extract_year(self, date_str: str) -> Optional[str]:
        """Extract 4-digit year from date string."""
        match = re.search(r'(\d{4})', date_str)
        return match.group(1) if match else None

    def _normalize_author(self, author: str) -> Optional[str]:
        """Extract last name from author string."""
        # Handle formats: "John Smith", "Smith, John", "Smith"
        author = author.strip()
        if ',' in author:
            return author.split(',')[0].strip().lower()
        parts = author.split()
        return parts[-1].lower() if parts else None

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = self._SENTENCE_SPLIT.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _find_citations(self, sentence: str) -> List[Dict]:
        """Find all citations in a sentence."""
        citations = []

        for pattern, cit_type in self._CITATION_PATTERNS:
            for match in pattern.finditer(sentence):
                citations.append({
                    'type': cit_type,
                    'match': match,
                    'text': match.group(0),
                })

        return citations

    def _build_claim(self, sentence_idx: int, sentences: List[str]) -> Optional[str]:
        """Build claim text with context (current + previous sentence).

        Returns None if the sentence appears to be a section header or non-claim text.
        """
        current = sentences[sentence_idx]

        # Skip section headers (e.g., "2 RELATED WORK", "2.1 Methodology")
        if self._is_header(current):
            return None

        # Skip very short sentences (likely not claims)
        if len(current) < 30:
            return None

        parts = []

        # Previous sentence if exists and not a header
        if sentence_idx > 0:
            prev = sentences[sentence_idx - 1]
            if not self._is_header(prev) and len(prev) >= 20:
                parts.append(prev)

        # Current sentence with citation
        parts.append(current)

        return ' '.join(parts)

    def _is_header(self, text: str) -> bool:
        """Check if text is likely a section header."""
        text = text.strip()
        if not text:
            return False

        # Check for figure/table captions first (fast path)
        if self._FIGURE_TABLE.match(text):
            return True

        # Remove citations for header detection
        no_cit = self._CITATION_BRACKETS.sub('', text).strip()

        # Check numbered header: "2 RELATED WORK", "3.1 Method"
        if self._HEADER_NUMBERED.match(no_cit):
            words = no_cit.split()
            if len(words) <= 6 and len(no_cit) < 80:
                return True

        # Check all-caps header: "REFERENCES", "INTRODUCTION"
        if self._HEADER_ALL_CAPS.match(no_cit) and len(no_cit) < 50:
            return True

        return False

    def _associate_claims(
        self,
        citations: List[Dict],
        claim: str,
        index: Dict[str, Paper],
        author_index: Dict[Tuple[str, str], List[Paper]],
    ) -> None:
        """Associate citations to papers with deduplication."""
        seen: Set[str] = set()  # Track papers that already have this claim

        for citation in citations:
            cit_type = citation['type']

            if cit_type in ('numeric', 'numeric_range'):
                nums = self._parse_numeric(citation['text'])
                for num in nums:
                    if num in index:
                        paper = index[num]
                        if paper.id not in seen:
                            paper.claims.append(claim)
                            seen.add(paper.id)

            elif cit_type == 'author_year':
                parsed = self._parse_author_year(citation['text'])
                if parsed:
                    key = (parsed['author'], parsed['year'])
                    if key in author_index:
                        for paper in author_index[key]:
                            if paper.id not in seen:
                                paper.claims.append(claim)
                                seen.add(paper.id)

    def _parse_numeric(self, citation_text: str) -> List[str]:
        """Parse numeric citation like [1,2,3] or [1-3] into list of numbers."""
        nums = []
        content = citation_text.strip('[]()')

        # Handle ranges: 1-3
        if '-' in content:
            try:
                start, end = map(int, content.split('-'))
                nums.extend(str(i) for i in range(start, end + 1))
            except ValueError:
                pass
        else:
            # Handle comma-separated: 1,2,3
            for part in content.split(','):
                part = part.strip()
                if part.isdigit():
                    nums.append(part)

        return nums

    def _parse_author_year(self, citation_text: str) -> Optional[Dict]:
        """Parse author-year citation like (Smith et al., 2024)."""
        content = citation_text.strip('()')
        # Split on comma, but only the last comma (year separator)
        parts = content.rsplit(',', 1)

        if len(parts) == 2:
            author_part = parts[0].strip()
            year = parts[1].strip()

            # Extract first author surname (handle "et al.", "and", prefixes)
            # Examples: "Smith et al.", "Smith and Jones", "de la Cruz", "OpenAI"
            author_key = self._extract_author(author_part)

            if author_key:
                return {'author': author_key, 'year': year}

        return None

    def _extract_author(self, author_str: str) -> Optional[str]:
        """Extract first author surname from author-year citation."""
        # Remove "et al."
        author_str = re.sub(r'\s+et\s+al\.?', '', author_str, flags=re.IGNORECASE)

        # Split by "and" for multiple authors
        parts = re.split(r'\s+and\s+', author_str, flags=re.IGNORECASE)
        first_author = parts[0].strip()

        if not first_author:
            return None

        # Normalize to lowercase for matching
        return first_author.lower()

    async def extract_batch(self, texts: List[str]) -> List[List[Paper]]:
        """Extract lists of referenced papers from a batch of text strings."""
        results = []
        for text in texts:
            results.append(await self.extract(text))
        return results


class PDFExtractor(Extractor):
    def __init__(self, text_extractor: Optional[TextExtractor] = None):
        self.text_extractor = (
            text_extractor if text_extractor is not None else TextExtractor()
        )

    async def extract(
        self,
        file_path: str,
        on_progress: Optional[Callable[[int, List[Reference]], None]] = None,
    ) -> List[Paper]:
        """
        Extract a list of referenced papers from a PDF file path.
        If on_progress is provided, streams partial results during extraction.
        """
        try:
            with fitz.open(file_path) as doc:
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                text = "".join(text_parts)
        except Exception as e:
            raise ExtractionError(
                message=f"Failed to open PDF file: {str(e)}",
                error_code=ErrorCode.PDF_CORRUPTED
            ) from e

        return await self.text_extractor.extract(text, on_progress=on_progress)

    async def extract_batch(self, file_paths: List[str]) -> List[List[Paper]]:
        """Extract lists of referenced papers from a batch of PDF file paths."""
        results = []
        for file_path in file_paths:
            results.append(await self.extract(file_path))
        return results
