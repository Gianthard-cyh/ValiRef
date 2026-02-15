import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration variables
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# LLM Constants
TEMP = 0.7
MAX_TOKENS = 4096
TIMEOUT = 60
MAX_RETRIES = 2

# Extraction Constants
EXTRACTION_CHAR_LIMIT = 20000
