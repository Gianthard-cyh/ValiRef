TEMP = 0.0
MAX_TOKENS = 4096
TIMEOUT = 60
MAX_RETRIES = 2

class Benchmark:
    def __init__(self, model: ChatDeepSeek):
        self.model = model

