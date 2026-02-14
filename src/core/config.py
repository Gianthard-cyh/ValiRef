import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration variables
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
