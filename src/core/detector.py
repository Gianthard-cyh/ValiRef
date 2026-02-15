from typing import List
from pydantic import BaseModel, Field
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

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
from .tools import ArxivSearch, ScholarlySearch
from .logger import logger


class ValidationResult(BaseModel):
    is_hallucination: bool = Field(
        description="True if the reference is likely a hallucination"
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Explanation for the judgment")
    evidence: List[str] = Field(
        default_factory=list,
        description="Links or titles found that support the judgment",
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
        self.scholar_search_instance = ScholarlySearch()

        # Define tools for the agent
        self.tools = [
            StructuredTool.from_function(
                func=self.arxiv_search_instance.search,
                name="arxiv_search",
                description="Search ArXiv for papers matching the query. Useful for finding physics, computer science, and math papers. Returns a list of dictionaries with paper details.",
            ),
            StructuredTool.from_function(
                func=self.scholar_search_instance.search,
                name="scholar_search",
                description="Search Google Scholar for papers matching the query. Useful for finding papers from a wide range of academic disciplines. NOTE: This tool is rate-limited to 1 request every 20 seconds. Returns a list of dictionaries with paper details.",
            ),
        ]

        # Initialize Agent
        self.agent_executor = create_react_agent(self.llm, self.tools)

    def check_reference(self, reference: Paper) -> ValidationResult:
        """
        Check if a single reference is valid or hallucinated using a ReAct Agent.
        """
        logger.info(f"Checking reference: {reference.title}")

        system_prompt = (
            "You are a scientific fact-checker. Your task is to verify if a given reference is a REAL publication.\n"
            "You have access to 'arxiv_search' and 'scholar_search' tools.\n"
            "Steps:\n"
            "1. Search for the paper using its title.\n"
            "2. If ArXiv fails, try Google Scholar (note: rate limited).\n"
            "3. Verify if the Title, Authors, and Date match the query.\n"
            "4. Be careful about Attribution Errors (real title but wrong authors).\n"
            "5. After gathering evidence, provide a final answer in JSON format matching the ValidationResult schema:\n"
            "   { 'is_hallucination': bool, 'confidence': float, 'reasoning': str, 'evidence': list[str] }\n"
            "Do NOT output markdown code blocks for the JSON. Just output the raw JSON string as the final answer."
        )

        user_prompt = (
            f"Target Reference:\n"
            f"Title: {reference.title}\n"
            f"Authors: {', '.join(reference.authors)}\n"
            f"Date: {reference.published_date}\n"
            f"ArXiv ID: {reference.id}\n"
            f"Venue: {reference.venue or 'N/A'}\n"
        )

        try:
            # Invoke the agent
            response = self.agent_executor.invoke(
                {
                    "messages": [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ]
                }
            )

            # Extract the last message content which should be the JSON
            last_message = response["messages"][-1]
            content = last_message.content

            # Parse JSON
            # Ideally we should use structured output, but create_react_agent is flexible.
            # Let's try to parse the string.
            import json
            import re

            # Clean up markdown code blocks if present
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*", "", content)
            content = content.strip()

            # Find the first JSON object if there's extra text
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            data = json.loads(content)
            return ValidationResult(**data)

        except Exception as e:
            logger.error(f"Agent validation failed: {e}")
            return ValidationResult(
                is_hallucination=True,
                confidence=0.5,
                reasoning=f"Validation failed due to error: {e}",
                evidence=[],
            )
