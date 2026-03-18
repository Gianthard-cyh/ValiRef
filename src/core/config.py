import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

# Database Configuration
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "valiref")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "valiref_secret")
DB_NAME = os.environ.get("DB_NAME", "arxiv_db")

# Observability (LangSmith)
LANGCHAIN_TRACING_V2 = os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.environ.get("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.environ.get("LANGCHAIN_PROJECT", "ValiRef")

if LANGCHAIN_TRACING_V2 and not LANGCHAIN_API_KEY:
    raise ValueError(
        "LANGCHAIN_API_KEY is required when LANGCHAIN_TRACING_V2 is enabled"
    )

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

# Rate Limiting Configuration (Legacy - kept for backward compatibility)
SCHOLAR_RATE_LIMIT_CALLS = 1
SCHOLAR_RATE_LIMIT_PERIOD = 10.0  # Increased to avoid rate limits (was 0.5)
ARXIV_RATE_LIMIT_DELAY = 5.0  # Increased to be safe (was 4.0)
SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY = 3.0  # New setting for Semantic Scholar

# Token Bucket Rate Limiting (New)
# Rate in tokens per second (1/rate = seconds between requests)
TOKEN_BUCKET_RATE_ARXIV = (
    0.5  # 1 second interval (was 0.5, increased for better throughput)
)
TOKEN_BUCKET_RATE_SCHOLAR = 0.2  # 5 second interval (kept strict for Google Scholar)
TOKEN_BUCKET_RATE_SEMANTIC_SCHOLAR = 1.0  # 1 second interval
TOKEN_BUCKET_RATE_OPENREVIEW = 1.5  # 0.67 second interval (was 1.0, slightly increased)
TOKEN_BUCKET_RATE_OPENALEX = (
    3.0  # 0.33 second interval (was 2.0, increased for better throughput)
)
TOKEN_BUCKET_RATE_DUCKDUCKGO = (
    2.0  # 0.5 second interval (kept conservative to avoid blocking)
)
TOKEN_BUCKET_BURST_SIZE = (
    1  # Maximum burst size (was 1, increased to allow concurrent requests)
)

# Circuit Breaker Configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3  # Consecutive failures before opening (was 5, reduced for faster failure detection)
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = (
    15.0  # Seconds before attempting recovery (was 30, reduced for faster recovery)
)
CIRCUIT_BREAKER_HALF_OPEN_CALLS = (
    2  # Successful calls needed to close (was 3, reduced for faster verification)
)

# Queue Configuration
QUEUE_MAX_SIZE = 100  # Maximum queue size for backpressure

# Search Configuration
ARXIV_SEARCH_LIMIT = 3  # Was 5, reduced for faster response
SCHOLAR_SEARCH_LIMIT = 3
SEMANTIC_SCHOLAR_SEARCH_LIMIT = 5
OPENREVIEW_SEARCH_LIMIT = 3
OPENALEX_SEARCH_LIMIT = 3
DUCKDUCKGO_SEARCH_LIMIT = 2  # Was 3, reduced as web search is slower

# CrossEncoder Reranking Configuration
CROSSENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CROSSENCODER_DEVICE = "cpu"
CROSSENCODER_MAX_LENGTH = 512
RERANK_CANDIDATE_MULTIPLIER = 4  # Fetch Nx candidates for reranking
