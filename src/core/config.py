import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")

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
SCHOLAR_SEARCH_LIMIT = 3
