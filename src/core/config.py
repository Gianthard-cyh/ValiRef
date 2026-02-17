import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

# Observability (LangSmith)
LANGCHAIN_TRACING_V2 = os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.environ.get("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.environ.get("LANGCHAIN_PROJECT", "ValiRef")

if LANGCHAIN_TRACING_V2 and not LANGCHAIN_API_KEY:
    raise ValueError("LANGCHAIN_API_KEY is required when LANGCHAIN_TRACING_V2 is enabled")

# LLM Configuration
LLM_MODEL = "deepseek-chat"
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 4096
LLM_TIMEOUT = 60
LLM_MAX_RETRIES = 2

# Detector Configuration
DETECTOR_TEMPERATURE = 0.1  # Lower temperature for more deterministic reasoning

# Extraction Configuration
EXTRACTION_CHAR_LIMIT = 20000

# Rate Limiting Configuration
SCHOLAR_RATE_LIMIT_CALLS = 1
SCHOLAR_RATE_LIMIT_PERIOD = 0.5

# Search Configuration
ARXIV_SEARCH_LIMIT = 5
SCHOLAR_SEARCH_LIMIT = 5
SEMANTIC_SCHOLAR_SEARCH_LIMIT = 20
OPENREVIEW_SEARCH_LIMIT = 5
OPENALEX_SEARCH_LIMIT = 5
