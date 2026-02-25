from typing import List
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
    def __init__(self):
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

        # Initialize Aggregate Search Tool
        self.aggregate_search_instance = AggregateSearch()

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
            "You have access to an `aggregate_search` tool that can query multiple sources at once.\n"
            "Steps:\n"
            "1. Search for the paper using its title. Use `aggregate_search` with sources like ['arxiv', 'openalex'].\n"
            "2. If not found, try adding 'openreview' or 'duckduckgo' to the sources list.\n"
            "3. Verify if the Title, Authors, and Date match the query.\n"
            "4. Be careful about Attribution Errors (real title but wrong authors).\n"
            "5. Gather enough evidence to make a definitive judgment.\n"
            "6. Once you have a conclusion, YOU MUST CALL the `submit_validation_result` tool to submit your findings.\n"
            "   - is_hallucination: True if it's fake or attribution error, False if real.\n"
            "   - confidence: 0.0 to 1.0\n"
            "   - reasoning: Detailed explanation.\n"
            "   - evidence: List of URLs that support your judgment. If URL is not available, provide the source name."
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
            # Asynchronous invoke
            response = await self.agent_executor.ainvoke(
                {
                    "messages": [
                        SystemMessage(content=self._get_system_prompt()),
                        HumanMessage(content=user_prompt),
                    ]
                }
            )
            return self._parse_agent_response(response)

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
