import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from langchain_core.tools import StructuredTool

from ..bench.schema import Paper
from .config import (
    DEEPSEEK_API_KEY,
    LLM_MODEL,
    DETECTOR_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    LLM_MAX_RETRIES,
)
from .tools import AggregateSearchFactory
from .logger import logger

# Agent execution timeout in seconds
AGENT_TIMEOUT = 120


class ValidationResult(BaseModel):
    hallucination_type: str = Field(
        description="Category: 'Real', 'Fabrication', 'AttributionError', 'Irrelevance', or 'Counterfactual'"
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Explanation for the judgment")
    evidence: List[str] = Field(
        default_factory=list,
        description="URLs found that support the judgment",
    )

    # Computed property for backward compatibility
    @property
    def is_hallucination(self) -> bool:
        return self.hallucination_type != "Real"


class HallucinationDetector:
    def __init__(
        self,
        llm: Optional[ChatDeepSeek] = None,
        search=None,  # Accepts any search instance (LocalAggregateSearch, OnlineAggregateSearch, etc.)
    ):
        if llm is not None:
            self.llm = llm
        else:
            if DEEPSEEK_API_KEY is None:
                raise ValueError("DEEPSEEK_API_KEY is not set")

            self.llm = ChatDeepSeek(
                model=LLM_MODEL,
                temperature=DETECTOR_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                timeout=LLM_TIMEOUT,
                max_retries=LLM_MAX_RETRIES,
                api_key=DEEPSEEK_API_KEY,
            )

        # Initialize Aggregate Search Tool (injected or default)
        if search is not None:
            self.aggregate_search_instance = search
        else:
            # Default to local search for better performance
            self.aggregate_search_instance = AggregateSearchFactory.create("local")

        self.tools = self._get_tools()
        self.agent_executor = create_agent(self.llm, self.tools)

    def _get_tools(self) -> List[StructuredTool]:
        """Initialize and return the list of tools available to the agent."""
        return [
            StructuredTool.from_function(
                func=None,
                coroutine=self.aggregate_search_instance.asearch,
                name="aggregate_search",
                description=(
                    "Search multiple sources concurrently for papers matching the query. "
                    "Sources can be a list of: 'arxiv', 'openreview', 'openalex', 'duckduckgo'. "
                    "Returns a combined list of paper details."
                ),
            ),
            StructuredTool.from_function(
                func=self._create_validation_result,
                name="submit_validation_result",
                description="Submit the final validation result. Use this tool to finalize your judgment.",
                return_direct=True,
            ),
        ]

    @staticmethod
    def _create_validation_result(
        hallucination_type: str,
        confidence: float,
        reasoning: str,
        evidence: List[str],
    ) -> ValidationResult:
        """
        Submit the final validation result for the reference check.

        Args:
            hallucination_type: One of 'Real', 'Fabrication', 'AttributionError',
                               'Irrelevance', or 'Counterfactual'
            confidence: Confidence score between 0.0 and 1.0
            reasoning: Explanation for the judgment
            evidence: URLs found that support the judgment
        """
        # Validate input
        valid_types = {"Real", "Fabrication", "AttributionError", "Irrelevance", "Counterfactual"}
        if hallucination_type not in valid_types:
            raise ValueError(
                f"Invalid hallucination_type: {hallucination_type}. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        return ValidationResult(
            hallucination_type=hallucination_type,
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence,
        )

    def _get_system_prompt(self) -> str:
        return (
            "You are a scientific fact-checker. Verify if a reference is REAL or HALLUCINATED.\n"
            "You have access to aggregate_search to query academic databases.\n"
            "\n"
            "Classification Categories (choose EXACTLY ONE):\n"
            "- **Real**: Paper exists, authors match, claims are consistent with paper content\n"
            "- **Fabrication**: Paper does not exist (search returns no results)\n"
            "- **AttributionError**: Paper exists BUT authors don't match (completely different names)\n"
            "- **Irrelevance**: Paper exists, authors match, BUT claims don't match paper's content\n"
            "- **Counterfactual**: Paper exists, authors match, BUT claims are opposite of paper's conclusions\n"
            "\n"
            "Instructions:\n"
            "1. Search using paper title OR ArXiv ID if available\n"
            "2. Examine ALL search results returned (not just the first one)\n"
            "3. Compare titles allowing for minor variations (capitalization, punctuation)\n"
            "4. Verify author names - the listed authors should be a SUBSET of actual authors\n"
            "5. Check claims consistency with abstract/content\n"
            "6. Call submit_validation_result with hallucination_type='CategoryName'\n"
            "\n"
            "IMPORTANT:\n"
            "- You MUST specify the exact hallucination_type: Real, Fabrication, AttributionError, "
            "Irrelevance, or Counterfactual\n"
            "- Partial author lists are ACCEPTABLE (e.g., first 3 authors of 7). Only flag if names are WRONG.\n"
            "- If search returns multiple results, check each one. Target paper may be result #2 or #3.\n"
            "- Do NOT keep searching once you find a matching paper - verify and submit.\n"
        )

    def _parse_agent_response(self, response: dict) -> ValidationResult:
        """
        Extract the ValidationResult from the agent's response.
        Handles both return_direct artifacts and tool calls.
        """
        messages = response.get("messages", [])
        if not messages:
            return ValidationResult(
                hallucination_type="Fabrication",  # Default to Fabrication on error
                confidence=0.0,
                reasoning="Agent returned no messages.",
                evidence=[],
            )

        last_message = messages[-1]

        if hasattr(last_message, "artifact") and last_message.artifact:
            if isinstance(last_message.artifact, ValidationResult):
                return last_message.artifact

        for message in reversed(messages):
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call["name"] == "submit_validation_result":
                        try:
                            args = tool_call["args"]
                            # Handle legacy format with is_hallucination
                            if "hallucination_type" not in args:
                                is_hallu = args.get("is_hallucination", True)
                                args["hallucination_type"] = "Fabrication" if is_hallu else "Real"
                            return ValidationResult(**args)
                        except Exception as e:
                            logger.error(f"Failed to parse tool args: {e}")

        logger.warning(
            "Agent did not call submit_validation_result. Returning inconclusive result."
        )
        return ValidationResult(
            hallucination_type="Fabrication",  # Default to Fabrication on error
            confidence=0.0,
            reasoning="Agent failed to submit a result.",
            evidence=[],
        )

    async def check_reference(self, reference: Paper) -> ValidationResult:
        """
        Check if a single reference is valid or hallucinated using a ReAct Agent
        asynchronously.
        """
        return await self.acheck_reference(reference)

    async def acheck_reference(self, reference: Paper) -> ValidationResult:
        """
        Check if a single reference is valid or hallucinated using a ReAct Agent
        asynchronously.
        """
        logger.info(f"Checking reference (async): {reference.title}")

        claims_text = "\n".join([f"  - {c}" for c in reference.claims]) if reference.claims else "  (none provided)"
        user_prompt = (
            f"Target Reference:\n"
            f"Title: {reference.title}\n"
            f"Authors: {', '.join(reference.authors)}\n"
            f"Date: {reference.published_date}\n"
            f"ArXiv ID: {reference.id}\n"
            f"Venue: {reference.venue or 'N/A'}\n"
            f"\n"
            f"Claims attributed to this reference:\n"
            f"{claims_text}\n"
        )

        try:
            # Asynchronous invoke with timeout to prevent infinite loops
            response = await asyncio.wait_for(
                self.agent_executor.ainvoke(
                    {
                        "messages": [
                            SystemMessage(content=self._get_system_prompt()),
                            HumanMessage(content=user_prompt),
                        ]
                    }
                ),
                timeout=AGENT_TIMEOUT,
            )
            return self._parse_agent_response(response)

        except asyncio.TimeoutError:
            logger.error(
                f"Agent timeout after {AGENT_TIMEOUT}s for: {reference.title[:50]}..."
            )
            return ValidationResult(
                hallucination_type="Fabrication",
                confidence=0.5,
                reasoning=f"Validation timeout after {AGENT_TIMEOUT}s - agent took too long to respond",
                evidence=[],
            )
        except KeyboardInterrupt:
            logger.warning("Validation interrupted by user.")
            raise
        except Exception as e:
            logger.error(f"Agent validation failed: {e}")
            return ValidationResult(
                hallucination_type="Fabrication",
                confidence=0.5,
                reasoning=f"Validation failed due to error: {e}",
                evidence=[],
            )
