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
from .tools import ArxivSearch, OpenReviewSearch, OpenAlexSearch
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

        # Initialize Search Tools
        self.arxiv_search_instance = ArxivSearch()
        # self.scholar_search_instance = ScholarlySearch() # Disabled due to rate limiting
        # self.semanticscholar_search_instance = SemanticScholarSearch() # Disabled due to rate limiting
        self.openreview_search_instance = OpenReviewSearch()
        self.openalex_search_instance = OpenAlexSearch()

        self.tools = self._get_tools()
        self.agent_executor = create_agent(self.llm, self.tools)

    def _get_tools(self) -> List[StructuredTool]:
        """Initialize and return the list of tools available to the agent."""
        return [
            StructuredTool.from_function(
                func=self.arxiv_search_instance.search,
                coroutine=self.arxiv_search_instance.asearch,
                name="arxiv_search",
                description="Search ArXiv for papers matching the query. Useful for finding physics, computer science, and math papers. Returns a list of dictionaries with paper details.",
            ),
            # StructuredTool.from_function(
            #     func=self.scholar_search_instance.search,
            #     coroutine=self.scholar_search_instance.asearch,
            #     name="scholar_search",
            #     description="Search Google Scholar for papers matching the query. Useful for finding papers from a wide range of academic disciplines. NOTE: This tool is rate-limited to 1 request every 20 seconds. Returns a list of dictionaries with paper details.",
            # ),
            # StructuredTool.from_function(
            #     func=self.semanticscholar_search_instance.search,
            #     coroutine=self.semanticscholar_search_instance.asearch,
            #     name="semanticscholar_search",
            #     description="Search Semantic Scholar for papers matching the query. Good for CS/AI papers. Returns a list of dictionaries with paper details.",
            # ),
            StructuredTool.from_function(
                func=self.openreview_search_instance.search,
                coroutine=self.openreview_search_instance.asearch,
                name="openreview_search",
                description="Search OpenReview for papers matching the query. Useful for finding papers in venues like NeurIPS, ICLR, ICML. Returns a list of dictionaries with paper details.",
            ),
            StructuredTool.from_function(
                func=self.openalex_search_instance.search,
                coroutine=self.openalex_search_instance.asearch,
                name="openalex_search",
                description="Search OpenAlex for papers matching the query. A very large open database of scientific papers. Returns a list of dictionaries with paper details.",
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
            "You have access to multiple search tools: 'arxiv_search', 'openreview_search', and 'openalex_search'.\n"
            "Steps:\n"
            "1. Search for the paper using its title. Start with 'arxiv_search' or 'openalex_search' as they are fast.\n"
            "2. If not found, try 'openreview_search' (for recent AI conferences).\n"
            "3. Verify if the Title, Authors, and Date match the query.\n"
            "4. Be careful about Attribution Errors (real title but wrong authors).\n"
            "5. Gather enough evidence to make a definitive judgment.\n"
            "6. Once you have a conclusion, YOU MUST CALL the `submit_validation_result` tool to submit your findings.\n"
            "   - is_hallucination: True if it's fake or attribution error, False if real.\n"
            "   - confidence: 0.0 to 1.0\n"
            "   - reasoning: Detailed explanation.\n"
            "   - evidence: List of found links or titles."
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
            response = await self.agent_executor.ainvoke(
                {
                    "messages": [
                        SystemMessage(content=self._get_system_prompt()),
                        HumanMessage(content=user_prompt),
                    ]
                }
            )
            return self._parse_agent_response(response)
        except Exception as e:
            logger.error(f"Agent validation failed: {e}")
            return ValidationResult(
                is_hallucination=True,
                confidence=0.5,
                reasoning=f"Validation failed due to error: {e}",
                evidence=[],
            )
