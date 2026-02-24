from confluent_kafka import Consumer, Producer
import json
import time
import requests
import sys
import os

# Add parent directory to Python path to import common module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.kafka_config import CONSUMER_CONFIG, PRODUCER_CONFIG, TOPIC

# Model configuration
MODEL_ENDPOINT = "https://llama70b-deploy-predictor-pankaj-rawat-hp-c8660003.pcai.si18.vcfmr.local"
API_PATH = "/v1/chat/completions"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IkhQeXNRVVBjeUZ5RmNMWU9VSGNiYk5TUGlRT0xxNWJxb3R6MHBwZ3JMVlEifQ.eyJhdWQiOlsiYXBpIiwiaXN0aW8tY2EiXSwiZXhwIjoxNzc0NDUzNzU2LCJpYXQiOjE3NDg1MzM3NTYsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiNTBkMTU2ZWEtMzkyYi00NjBkLThiY2QtNTE0MGM5MDMwY2Y0Iiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJ1aSIsInNlcnZpY2VhY2NvdW50Ijp7Im5hbWUiOiJpc3ZjLWVwLTE3NDg1MzM3NTY4ODAiLCJ1aWQiOiIzOTE1ZmFjOS01ZjI2LTRjYzUtOTBjMS05NDZmN2U5MTk0NTYifX0sIm5iZiI6MTc0ODUzMzc1Niwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OnVpOmlzdmMtZXAtMTc0ODUzMzc1Njg4MCJ9.WMXxihq-1Wia_DajqhShbNQ0J_titbGAECR2nFfPFm4xckQ2ALV6nHsdOnaTIxZj-8pZUiMnkK_7WXFrL4_y2EYzqhmkpZ6h6t994dmdCIIhWbYobzE91w7IhABp9dQSiezyP3g4Ei-3dbFAJvXULXFT9MR-HrihzudYOkhBCANG3J4gEK3eTpoozBVeAijMnPMlWWpAiucRsYjW8JDoFJtxAnoL0jIKxUg1x9bnMHe1h77otDoXXvtpkMmr9Ih-k60XZm5FkilM4Q2kWhxOScKpR8Gtkn5CZuyXBCCyYz_v5C0HpCLGJrE7l0gk1LtrMbrfiDaknRZQu50Q1GDFNw"

SUMMARY_PROMPT = (
    "Analyze the following Jenkins build log, with a focus on the pytest execution output. Identify and summarize:\n\n"
    "**Failed test cases** along with their names and file locations.\n\n"
    "**Selectors or locators** that caused the failures (e.g., CSS/XPath), and specify where in the code (file/function) they are defined or referenced, if visible.\n\n"
    "**Any tracebacks or error messages** related to element not found, timeout, or assertion errors.\n\n"
    "**Group the findings** to help testers quickly backtrack in the browser and debug.\n\n"
    "Format your response in a structured way that makes it easy for testers to understand what failed and where to look for fixes.\n\n"
    "Jenkins build log to analyze:\n\n"
)
TOKENS_PER_CHUNK = 100000
CHARS_PER_TOKEN = 4  # Safe estimate
CHUNK_SIZE = TOKENS_PER_CHUNK * CHARS_PER_TOKEN  # 400,000 characters

def split_by_chars(text, chunk_size):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def summarize_chunk(chunk):
    prompt = SUMMARY_PROMPT + chunk
    BODY_DATA = {
        "model": "meta/llama-3.1-70b-instruct",
        "messages": [
            { "role": "system", "content": "You are a data analysis expert" },
            { "role": "user", "content": prompt }
        ],
        "max_tokens": 1024
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }
    try:
        response = requests.post(
            f"{MODEL_ENDPOINT}{API_PATH}",
            headers=headers,
            data=json.dumps(BODY_DATA),
            verify=False
        )
        resp_json = response.json()
        return resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"[ERROR] Failed to summarize chunk: {str(e)}"

def iterative_summarize(text, chunk_size=CHUNK_SIZE):
    """
    Repeatedly splits text into character-based chunks, summarizes each chunk, and then summarizes the summaries,
    until the result fits in one chunk.
    """
    while len(text) > chunk_size:
        chunks = split_by_chars(text, chunk_size)
        chunk_summaries = []
        for chunk in chunks:
            summary = summarize_chunk(chunk)
            chunk_summaries.append(summary)
        text = "\n\n".join(chunk_summaries)
    # Final summary
    return summarize_chunk(text)

def summarize_with_llama(log):
    try:
        return iterative_summarize(log)
    except Exception as e:
        return f"[LLaMA CONNECTION ERROR]: {str(e)}"

agent_consumer_config = CONSUMER_CONFIG.copy()
agent_consumer_config['group.id'] = 'ai-agent-group'  # Dedicated group for AI agent
consumer = Consumer(agent_consumer_config)
consumer.subscribe([TOPIC])

producer = Producer(PRODUCER_CONFIG)

print("[AI AGENT] Listening for Jenkins logs...")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"[AGENT] Error: {msg.error()}")
        continue

    try:
        data = json.loads(msg.value().decode("utf-8"))
        if data["response_payload"]:
            continue  # already processed

        print(f"[AGENT] Processing request_id: {data['request_id']}")
        log_content = data["request_payload"]
        print(f"[AGENT] Log content length: {len(str(log_content))} characters")
        
        # Check if log_content looks like actual log content vs just a number
        if isinstance(log_content, (int, float)) or (isinstance(log_content, str) and log_content.isdigit()):
            print(f"[AGENT] ⚠️  Warning: Received what appears to be a build number ({log_content}) instead of log content")
            summary = f"[ERROR] Received build number ({log_content}) instead of actual Jenkins log content. Please check the client implementation."
        else:
            summary = summarize_with_llama(log_content)

        data["response_payload"] = summary
        data["timestamp"] = time.time()
        print(data["response_payload"][:1000])  

        producer.produce(TOPIC, key=data["request_id"], value=json.dumps(data))
        producer.flush()
        print(f"[AGENT] ✅ Responded: {data['request_id']}")

    except Exception as e:
        print("[AGENT] Failed to process message:", e)

consumer.close()
