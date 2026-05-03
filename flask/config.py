"""Centralised configuration: environment, MongoDB, LLM client, constants."""

import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient

# Allow imports from the parent directory (common/)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.llm_client import LLMClient, LLMClientConfig, env_bool

# Environment

_FLASK_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_LOCAL = os.path.join(_FLASK_DIR, ".env.local")

if os.path.exists(_ENV_LOCAL):
    load_dotenv(_ENV_LOCAL)
    print("[CONFIG] Using .env.local")
else:
    load_dotenv(os.path.join(_FLASK_DIR, ".env"))
    print("[CONFIG] Using .env")

# MongoDB

MONGO_USER = os.getenv("MONGO_USER", "")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "jenkins")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")


def _connect_mongo() -> tuple:
    """Try remote MongoDB, then fall back to localhost."""
    conn_str = (
        f"mongodb://{quote_plus(MONGO_USER)}:{quote_plus(MONGO_PASSWORD)}"
        f"@{MONGO_HOST}:{MONGO_PORT}/{MONGO_AUTH_DB}"
    )
    timeout = dict(serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000)

    # Remote
    try:
        cli = MongoClient(conn_str, **timeout)
        cli.server_info()
        _db = cli[MONGO_DB]
        _db["jobs"].find_one()
        print(f"[CONFIG] MongoDB connected ({MONGO_HOST}:{MONGO_PORT})")
        return cli, _db, _db["jobs"]
    except Exception as exc:
        print(f"[CONFIG] Remote MongoDB failed: {exc}")

    # Local fallback
    try:
        cli = MongoClient("mongodb://localhost:27017/")
        cli.server_info()
        _db = cli["jenkins"]
        print("[CONFIG] MongoDB fallback → localhost:27017")
        return cli, _db, _db["jobs"]
    except Exception as exc:
        print(f"[CONFIG] Local MongoDB failed: {exc}")
        raise RuntimeError("Cannot connect to any MongoDB instance")


client, db, jobs_collection = _connect_mongo()
analyses_collection = db["analyses"]
feedback_collection = db["feedback"]
embeddings_collection = db["embeddings"]

# Ensure vector-search index exists for RAG
try:
    embeddings_collection.create_index("analysis_id", unique=True, sparse=True)
    embeddings_collection.create_index("job_name")
except Exception:
    pass

# LLM Client

# GitHub Copilot / OpenAI SDK configuration
COPILOT_API_URL = os.getenv("COPILOT_API_URL", "https://api.githubcopilot.com")
COPILOT_API_KEY = os.getenv("COPILOT_API_KEY", os.getenv("GITHUB_TOKEN", ""))
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
LLM_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

# Keep LLM_API_URL / LLM_AUTH_TOKEN as aliases for backwards compat
LLM_API_URL = COPILOT_API_URL
LLM_AUTH_TOKEN = COPILOT_API_KEY

llm_client = LLMClient(
    LLMClientConfig(
        api_url=COPILOT_API_URL,
        auth_token=COPILOT_API_KEY,
        default_model=LLM_MODEL_NAME,
        provider="copilot",
        timeout_seconds=LLM_TIMEOUT,
        max_retries=LLM_RETRIES,
    )
)

if llm_client.is_configured():
    print(f"[CONFIG] LLM ready (provider=copilot, model={LLM_MODEL_NAME})")
else:
    print("[CONFIG] LLM not configured — set COPILOT_API_KEY (or GITHUB_TOKEN) and LLM_MODEL_NAME")

# Constants

TOKENS_PER_CHUNK = 60_000
CHARS_PER_TOKEN = 4
CHUNK_SIZE = TOKENS_PER_CHUNK * CHARS_PER_TOKEN  # 240 000 chars
CHUNK_OVERLAP = 1_000

FREQUENCY_MAP = {
    "daily": "0 9 * * *",
    "weekly": "0 9 * * 1",
    "monthly": "0 9 1 * *",
    "hourly": "0 * * * *",
}

# RAG settings
RAG_TOP_K = 3                          # number of similar analyses to retrieve
RAG_SIMILARITY_THRESHOLD = 0.65        # minimum cosine similarity
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ReAct settings
REACT_MAX_ITERATIONS = 3               # max self-correction loops
REACT_CONFIDENCE_THRESHOLD = 55        # re-evaluate if below this
