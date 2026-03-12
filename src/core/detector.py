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
from .tools import AggregateSearch
from .logger import logger

# Agent execution timeout in seconds
AGENT_TIMEOUT = 60


class ValidationResult(BaseModel):
    is_hallucination: bool = Field(
        description="True if the reference is likely a hallucination"
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Explanation for the judgment")
    evidence: List[str] = Field(
        default_factory=list,
        description="URLs found that support the judgment",
    )


class HallucinationDetector:
    def __init__(
        self,
        llm: Optional[ChatDeepSeek] = None,
        search: Optional[AggregateSearch] = None,
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
        self.aggregate_search_instance = search if search is not None else AggregateSearch()

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
        is_hallucination: bool,
        confidence: float,
        reasoning: str,
        evidence: List[str],
    ) -> ValidationResult:
        """
        Submit the final validation result for the reference check.
        Call this tool when you have gathered enough evidence and made a decision.
        """
        return ValidationResult(
            is_hallucination=is_hallucination,
            confidence=confidence,
            reasoning=reasoning,
            evidence=evidence,
        )

    def _get_system_prompt(self) -> str:
        return (
            "You are a scientific fact-checker. Your task is to verify if a given reference is a REAL publication.\n"
            "You have access to an `aggregate_search` tool that can query multiple sources concurrently.\n"
            "\n"
            "Available sources and when to use them:\n"
            "- 'openalex': PRIMARY source for all academic papers - broad coverage, no rate limits, always start with this\n"
            "- 'openreview': For ICLR/NeurIPS/ICML/ACL conference papers, or when venue suggests these conferences\n"
            "- 'arxiv': ONLY when the reference explicitly mentions an arXiv ID or 'arXiv' in the venue/title\n"
            "- 'duckduckgo': Fallback when academic sources return no results\n"
            "\n"
            "Search strategy:\n"
            "1. Use the paper title as the search query (direct paste works best)\n"
            "2. Select sources based on the reference context:\n"
            "   - General paper / unknown venue → ['openalex']\n"
            "   - ML/AI conference paper → ['openalex', 'openreview']\n"
            "   - Has arXiv ID → add 'arxiv'\n"
            "3. If no results, try broader search (remove subtitle after colon, or use first 5-6 words)\n"
            "4. Verify Title, Authors, and Date match. Watch for Attribution Errors\n"
            "5. Once you have enough evidence, YOU MUST CALL `submit_validation_result`\n"
        )

    def _parse_agent_response(self, response: dict) -> ValidationResult:
        """
        Extract the ValidationResult from the agent's response.
        Handles both return_direct artifacts and tool calls.
        """
        messages = response.get("messages", [])
        if not messages:
            return ValidationResult(
                is_hallucination=True,
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
                            return ValidationResult(**args)
                        except Exception as e:
                            logger.error(f"Failed to parse tool args: {e}")

        logger.warning(
            "Agent did not call submit_validation_result. Returning inconclusive result."
        )
        return ValidationResult(
            is_hallucination=True,
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

        user_prompt = (
            f"Target Reference:\n"
            f"Title: {reference.title}\n"
            f"Authors: {', '.join(reference.authors)}\n"
            f"Date: {reference.published_date}\n"
            f"ArXiv ID: {reference.id}\n"
            f"Venue: {reference.venue or 'N/A'}\n"
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
                is_hallucination=True,
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
                is_hallucination=True,
                confidence=0.5,
                reasoning=f"Validation failed due to error: {e}",
                evidence=[],
            )
