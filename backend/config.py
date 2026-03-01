import os

class Config:
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = 6379
    DATA_DIR = "/app/data_output"
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    AUTH_TOKEN_TTL_SECONDS = int(os.getenv('AUTH_TOKEN_TTL_SECONDS', '604800'))