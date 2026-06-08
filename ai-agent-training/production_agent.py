import os
import time
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

load_dotenv()

# ==========================================
# 1. Configuration & Client Setup
# ==========================================
def get_base_url(raw_endpoint: str) -> str:
    base = raw_endpoint.rstrip("/")
    if "/api/projects/" in base:
        return f"{base.split('/api/projects/')[0]}/openai/v1"
    if base.endswith("/models"):
        return base.rsplit("/models", 1)[0] + "/openai/v1"
    if not base.endswith("/openai/v1"):
        return f"{base}/openai/v1"
    return base

client = OpenAI(
    api_key=os.getenv("FOUNDRY_API_KEY"),
    base_url=get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))
)

CHAT_MODEL = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-3-small"

# ==========================================
# 2. Semantic Cache Setup
# ==========================================
# In production, this would be Redis or a specialized Vector DB.
# We use an in-memory list for this lab: [{"embedding": [...], "response": "..."}]
semantic_cache = []
SIMILARITY_THRESHOLD = 0.92  # 92% similarity required for a cache hit

def cosine_similarity(vec_a, vec_b):
    """Calculates the mathematical distance between two vectors."""
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    return dot_product / (norm_a * norm_b)

# ==========================================
# 3. LLM Logic with Exponential Backoff
# ==========================================
# If the API hits a Rate Limit (429), wait 2s, then 4s, then 8s, up to 5 attempts.
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitError),
    before_sleep=lambda retry_state: print(f"  [Warning] Rate limited! Retrying in {retry_state.next_action.sleep}s...")
)
def call_llm(prompt: str) -> str:
    print("  [System] Sending request to Azure OpenAI...")
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# ==========================================
# 4. The Main Agent Loop
# ==========================================
def ask_agent(user_query: str):
    print(f"\nUser: {user_query}")
    start_time = time.time()
    
    # Step 1: Convert the query into a vector
    embed_res = client.embeddings.create(input=user_query, model=EMBEDDING_MODEL)
    query_vector = embed_res.data[0].embedding
    
    # Step 2: Check the Semantic Cache
    for cached_item in semantic_cache:
        similarity = cosine_similarity(query_vector, cached_item["embedding"])
        
        if similarity >= SIMILARITY_THRESHOLD:
            print(f"  [CACHE HIT!] Semantic match found (Score: {similarity:.3f})")
            print(f"Agent: {cached_item['response']}")
            print(f"Latency: {(time.time() - start_time):.3f} seconds\n" + "-"*50)
            return

    # Step 3: Cache Miss. Call the LLM (with retry logic)
    print("  [CACHE MISS] No similar queries found. Generating new answer.")
    answer = call_llm(user_query)
    
    # Step 4: Save the new answer and its vector to the cache
    semantic_cache.append({
        "embedding": query_vector,
        "response": answer
    })
    
    print(f"Agent: {answer}")
    print(f"Latency: {(time.time() - start_time):.3f} seconds\n" + "-"*50)


if __name__ == "__main__":
    print("--- Testing Semantic Cache & Resilience ---")
    
    # Query 1: The initial query (Cache Miss)
    ask_agent("How do I reset my corporate password?")
    
    # Query 2: Exact same query (Exact Match Cache Hit)
    ask_agent("How do I reset my corporate password?")
    
    # Query 3: Paraphrased query (Semantic Cache Hit!)
    ask_agent("I forgot my login password, what is the reset process?")
    
    # Query 4: Unrelated query (Cache Miss)
    ask_agent("What is the capital of Japan?")
