import os
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

load_dotenv()

# ==========================================
# 1. Configuration & Client Setup
# ==========================================
def get_base_url(raw_endpoint: str) -> str:
    base = raw_endpoint.rstrip("/")
    if "/api/projects/" in base:
        resource_base = base.split("/api/projects/")[0]
        return f"{resource_base}/openai/v1"
    if base.endswith("/models"):
        return base.rsplit("/models", 1)[0] + "/openai/v1"
    if not base.endswith("/openai/v1"):
        return f"{base}/openai/v1"
    return base

api_key = os.getenv("FOUNDRY_API_KEY")
base_url = get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))

oai_client = OpenAI(api_key=api_key, base_url=base_url)
CHAT_MODEL = os.getenv("FOUNDRY_DEPLOYMENT", "gpt-4o")
EMBEDDING_MODEL = os.getenv("FOUNDRY_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
EMBEDDING_MAX_RETRIES = 5
EMBEDDING_RETRY_DELAY_SECONDS = 15

search_endpoint = os.getenv("SEARCH_ENDPOINT")
search_credential = AzureKeyCredential(os.getenv("SEARCH_ADMIN_KEY"))
INDEX_NAME = "employee-handbook-index"

search_client = SearchClient(endpoint=search_endpoint, index_name=INDEX_NAME, credential=search_credential)

# ==========================================
# 2. The Retrieval Function (Hybrid Search)
# ==========================================
def retrieve_context(user_question: str) -> str:
    print(f"  [System] Embedding user query and searching database...")
    
    # 1. Convert the user's question into a vector
    last_error = None
    for attempt in range(1, EMBEDDING_MAX_RETRIES + 1):
        try:
            embedding_response = oai_client.embeddings.create(
                input=user_question,
                model=EMBEDDING_MODEL,
            )
            query_vector = embedding_response.data[0].embedding
            break
        except Exception as e:
            last_error = e
            if "unavailable_model" not in str(e):
                raise e
            if attempt < EMBEDDING_MAX_RETRIES:
                print(
                    f"  [System] Embedding model not ready yet "
                    f"(attempt {attempt}/{EMBEDDING_MAX_RETRIES}). Retrying in "
                    f"{EMBEDDING_RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(EMBEDDING_RETRY_DELAY_SECONDS)
            else:
                print(f"\n  [ERROR] Azure could not find the '{EMBEDDING_MODEL}' deployment.")
                print("  [FIX] GlobalStandard deployments can take 5-15 minutes to sync after the portal shows Succeeded.")
                print("  [FIX] Confirm the deployment name in Foundry matches FOUNDRY_EMBEDDING_DEPLOYMENT in .env.")
                print("  [FIX] Wait a few minutes and try running the script again.")
                sys.exit(1)
    else:
        raise last_error
    
    # 2. Define the Vector Search query
    vector_query = VectorizedQuery(
        vector=query_vector, 
        k_nearest_neighbors=3, 
        fields="content_vector"
    )
    
    # 3. Execute the Hybrid Search (Text + Vector)
    results = search_client.search(
        search_text=user_question, # Keyword search
        vector_queries=[vector_query], # Semantic search
        select=["id", "content"], # Only return the readable text, not the massive vector array
        top=3
    )
    
    # 4. Concatenate the results into a single context string
    context_string = ""
    for result in results:
        context_string += f"- {result['content']}\n"
        
    return context_string
# ==========================================
# 3. The Generative Agent
# ==========================================
def ask_rag_agent(user_question: str):
    print(f"\nUser: {user_question}")
    
    # Step 1: Retrieve facts from the database
    retrieved_context = retrieve_context(user_question)
    
    if not retrieved_context.strip():
        print("  [System] No relevant documents found.")
        return "I'm sorry, but I couldn't find any information about that in the company database."
        
    print(f"  [System] Context Retrieved:\n{retrieved_context}")
    
    # Step 2: Build the grounded prompt
    system_prompt = f"""
    You are a helpful HR and IT assistant for Contoso Electronics.
    You must answer the user's question using ONLY the facts provided in the Context below.
    If the Context does not contain the answer, explicitly state "I don't know based on the provided policies."
    Do not use outside knowledge.
    
    CONTEXT:
    {retrieved_context}
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question}
    ]
    
    print("  [System] Generating grounded response...")
    
    # Step 3: Call the LLM
    response = oai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.0 # Determinism prevents hallucinations
    )
    
    print(f"\nAgent: {response.choices[0].message.content}")

if __name__ == "__main__":
    print("--- Testing RAG Agent ---")
    
    # Test 1: A question covered by our database
    ask_rag_agent("What is the company policy on alcohol during business trips?")
    print("-" * 50)
    
    # Test 2: A question outside of our database (Testing Grounding)
    ask_rag_agent("Who won the Superbowl last year?")
