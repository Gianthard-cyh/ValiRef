"""
Unit tests for src.core.detector module with dependency injection.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.core.detector import HallucinationDetector, ValidationResult
from src.bench.schema import Paper


class TestHallucinationDetector:
    """Tests for HallucinationDetector with dependency injection."""

    def test_constructor_with_mock_llm(self):
        """Test HallucinationDetector accepts mock LLM via constructor."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent"):
                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

        assert detector.llm == mock_llm

    def test_constructor_with_mock_search(self):
        """Test HallucinationDetector accepts mock AggregateSearch via constructor."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent"):
                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

        assert detector.aggregate_search_instance == mock_search

    def test_constructor_creates_default_tools_when_not_provided(self):
        """Test detector creates default dependencies when not injected."""
        mock_llm = MagicMock()

        with (
            patch("src.core.detector.AggregateSearchFactory") as mock_factory,
            patch.object(HallucinationDetector, "_get_tools", return_value=[]),
            patch("src.core.detector.create_agent"),
        ):
            mock_search = MagicMock()
            mock_factory.create.return_value = mock_search

            detector = HallucinationDetector(llm=mock_llm)

            assert detector.aggregate_search_instance == mock_search

    @pytest.mark.asyncio
    async def test_check_reference_with_mocked_agent(self):
        """Test check_reference with mocked agent."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        # Mock the agent executor
        mock_response = {
            "messages": [
                MagicMock(
                    tool_calls=[
                        {
                            "name": "submit_validation_result",
                            "args": {
                                "hallucination_type": "Real",
                                "confidence": 0.95,
                                "reasoning": "Found matching paper",
                                "evidence": ["http://example.com/paper"],
                            },
                        }
                    ]
                )
            ]
        }

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = AsyncMock(return_value=mock_response)
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="123",
                    title="Test Paper",
                    abstract="Abstract",
                    authors=["Author"],
                    published_date="2023",
                    url="http://example.com",
                )

                result = await detector.check_reference(paper)

                assert isinstance(result, ValidationResult)
                assert result.hallucination_type == "Real"
                assert result.is_hallucination is False  # Property should still work
                assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_check_reference_handles_agent_timeout(self):
        """Test check_reference raises ValidationTimeoutError on agent timeout."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = AsyncMock(side_effect=TimeoutError())
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="123",
                    title="Test Paper",
                    abstract="Abstract",
                    authors=["Author"],
                    published_date="2023",
                    url="http://example.com",
                )

                from src.core.exceptions import ValidationTimeoutError
                with pytest.raises(ValidationTimeoutError):
                    await detector.check_reference(paper)

    @pytest.mark.asyncio
    async def test_check_reference_handles_no_tool_calls(self):
        """Test check_reference raises AgentParseError when agent doesn't call submit_validation_result."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        # Response without proper tool call
        mock_response = {"messages": [MagicMock(tool_calls=[])]}

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = AsyncMock(return_value=mock_response)
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="123",
                    title="Test Paper",
                    abstract="Abstract",
                    authors=["Author"],
                    published_date="2023",
                    url="http://example.com",
                )

                from src.core.exceptions import AgentParseError
                with pytest.raises(AgentParseError):
                    await detector.check_reference(paper)


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_validation_result_creation(self):
        """Test ValidationResult can be created with all fields."""
        result = ValidationResult(
            hallucination_type="Real",
            confidence=0.95,
            reasoning="Paper found in OpenAlex",
            evidence=["https://openalex.org/works/W123"],
        )

        assert result.hallucination_type == "Real"
        assert result.is_hallucination is False  # Property computed from type
        assert result.confidence == 0.95
        assert result.reasoning == "Paper found in OpenAlex"
        assert result.evidence == ["https://openalex.org/works/W123"]

    def test_validation_result_hallucination_types(self):
        """Test ValidationResult correctly identifies hallucination types."""
        # Real paper
        real = ValidationResult(
            hallucination_type="Real",
            confidence=0.95,
            reasoning="Valid paper",
        )
        assert real.is_hallucination is False

        # Fabrication
        fab = ValidationResult(
            hallucination_type="Fabrication",
            confidence=0.9,
            reasoning="Paper does not exist",
        )
        assert fab.is_hallucination is True

        # AttributionError
        attr = ValidationResult(
            hallucination_type="AttributionError",
            confidence=0.85,
            reasoning="Wrong authors",
        )
        assert attr.is_hallucination is True

        # Irrelevance
        irr = ValidationResult(
            hallucination_type="Irrelevance",
            confidence=0.8,
            reasoning="Claims don't match",
        )
        assert irr.is_hallucination is True

        # Counterfactual
        counter = ValidationResult(
            hallucination_type="Counterfactual",
            confidence=0.75,
            reasoning="Opposite conclusion",
        )
        assert counter.is_hallucination is True

    def test_validation_result_unknown_type(self):
        """Test ValidationResult handles Unknown type for system errors."""
        unknown = ValidationResult(
            hallucination_type="Unknown",
            confidence=0.0,
            reasoning="Validation system error occurred",
        )
        assert unknown.hallucination_type == "Unknown"
        assert unknown.is_hallucination is True  # Treated as error state

    def test_validation_result_default_evidence(self):
        """Test ValidationResult creates empty evidence list by default."""
        result = ValidationResult(
            hallucination_type="Fabrication",
            confidence=0.8,
            reasoning="No evidence found",
        )

        assert result.evidence == []


class TestClaimAwareValidation:
    """Tests for claim-aware validation in HallucinationDetector."""

    def test_system_prompt_includes_claim_validation(self):
        """Test system prompt includes claim validation instructions."""
        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent"):
                detector = HallucinationDetector(llm=MagicMock(), search=MagicMock())
                prompt = detector._get_system_prompt()

        # Check for key claim validation sections
        assert "CLAIMS attributed to this reference" in prompt
        assert "Irrelevance" in prompt
        assert "Counterfactual" in prompt
        assert "claims are consistent" in prompt.lower() or "claims don't match" in prompt.lower()
        assert "MOST IMPORTANT: Verify the CLAIMS" in prompt

    def test_system_prompt_includes_decision_guide(self):
        """Test system prompt includes decision guide for different scenarios."""
        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent"):
                detector = HallucinationDetector(llm=MagicMock(), search=MagicMock())
                prompt = detector._get_system_prompt()

        # Check decision guide entries
        assert "Decision Guide:" in prompt
        assert "If no search results" in prompt
        assert "If found but authors" in prompt
        assert "If found, authors match, but claims are unrelated" in prompt
        assert "If found, authors match, but claims contradict" in prompt
        assert "If found, authors match, claims consistent" in prompt

    def test_system_prompt_categories_are_clear(self):
        """Test that hallucination categories are clearly defined."""
        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent"):
                detector = HallucinationDetector(llm=MagicMock(), search=MagicMock())
                prompt = detector._get_system_prompt()

        # All five categories should be defined
        assert "- **Real**:" in prompt
        assert "- **Fabrication**:" in prompt
        assert "- **AttributionError**:" in prompt
        assert "- **Irrelevance**:" in prompt
        assert "- **Counterfactual**:" in prompt

    @pytest.mark.asyncio
    async def test_check_reference_includes_claims_in_prompt(self):
        """Test that papers with claims are formatted correctly in user prompt."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        # Capture the invocation to verify prompt content
        captured_messages = {}

        async def capture_invoke(input_data):
            captured_messages["input"] = input_data
            return {
                "messages": [
                    MagicMock(
                        tool_calls=[
                            {
                                "name": "submit_validation_result",
                                "args": {
                                    "hallucination_type": "Irrelevance",
                                    "confidence": 0.85,
                                    "reasoning": "Paper exists but claims don't match",
                                    "evidence": ["http://example.com/paper"],
                                },
                            }
                        ]
                    )
                ]
            }

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = capture_invoke
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="123",
                    title="Test Paper",
                    abstract="Abstract",
                    authors=["Smith, John"],
                    published_date="2023",
                    url="http://example.com",
                    claims=["This paper proposes method X", "Method X outperforms Y by 20%"],
                )

                await detector.check_reference(paper)

                # Verify the prompt includes claims
                messages = captured_messages["input"]["messages"]
                human_message = messages[1]  # Second message is HumanMessage
                content = human_message.content

                assert "Claims attributed to this reference:" in content
                assert "This paper proposes method X" in content
                assert "Method X outperforms Y by 20%" in content

    @pytest.mark.asyncio
    async def test_check_reference_handles_empty_claims(self):
        """Test that papers without claims show '(none provided)'."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        captured_messages = {}

        async def capture_invoke(input_data):
            captured_messages["input"] = input_data
            return {
                "messages": [
                    MagicMock(
                        tool_calls=[
                            {
                                "name": "submit_validation_result",
                                "args": {
                                    "hallucination_type": "Real",
                                    "confidence": 0.9,
                                    "reasoning": "Valid paper",
                                    "evidence": [],
                                },
                            }
                        ]
                    )
                ]
            }

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = capture_invoke
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="123",
                    title="Test Paper",
                    abstract="Abstract",
                    authors=["Smith, John"],
                    published_date="2023",
                    url="http://example.com",
                    claims=[],  # Empty claims
                )

                await detector.check_reference(paper)

                messages = captured_messages["input"]["messages"]
                human_message = messages[1]
                content = human_message.content

                assert "Claims attributed to this reference:" in content
                assert "(none provided)" in content

    @pytest.mark.asyncio
    async def test_claim_aware_validation_result_irrelevance(self):
        """Test that Irrelevance result is correctly parsed for claim mismatch."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        mock_response = {
            "messages": [
                MagicMock(
                    tool_calls=[
                        {
                            "name": "submit_validation_result",
                            "args": {
                                "hallucination_type": "Irrelevance",
                                "confidence": 0.88,
                                "reasoning": "Paper exists about NLP but claims are about computer vision",
                                "evidence": ["https://openalex.org/works/W123"],
                            },
                        }
                    ]
                )
            ]
        }

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = AsyncMock(return_value=mock_response)
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="123",
                    title="NLP Techniques",
                    abstract="Abstract",
                    authors=["Smith, John"],
                    published_date="2023",
                    url="http://example.com",
                    claims=["This paper discusses image recognition"],
                )

                result = await detector.check_reference(paper)

                assert result.hallucination_type == "Irrelevance"
                assert result.is_hallucination is True
                assert "NLP" in result.reasoning or "computer vision" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_claim_aware_validation_result_counterfactual(self):
        """Test that Counterfactual result is correctly parsed for contradictory claims."""
        mock_llm = MagicMock()
        mock_search = MagicMock()

        mock_response = {
            "messages": [
                MagicMock(
                    tool_calls=[
                        {
                            "name": "submit_validation_result",
                            "args": {
                                "hallucination_type": "Counterfactual",
                                "confidence": 0.92,
                                "reasoning": "Paper concludes method A is better than B, but claim states B is better than A",
                                "evidence": ["https://openalex.org/works/W456"],
                            },
                        }
                    ]
                )
            ]
        }

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent") as mock_create_agent:
                mock_agent = MagicMock()
                mock_agent.ainvoke = AsyncMock(return_value=mock_response)
                mock_create_agent.return_value = mock_agent

                detector = HallucinationDetector(llm=mock_llm, search=mock_search)

                paper = Paper(
                    source="reference",
                    id="456",
                    title="Comparison Study",
                    abstract="Abstract",
                    authors=["Jones, Jane"],
                    published_date="2023",
                    url="http://example.com",
                    claims=["Method B significantly outperforms method A"],
                )

                result = await detector.check_reference(paper)

                assert result.hallucination_type == "Counterfactual"
                assert result.is_hallucination is True
                assert "better" in result.reasoning.lower() or "conclude" in result.reasoning.lower()
