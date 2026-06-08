import os
from dotenv import load_dotenv
from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator

load_dotenv()

def get_base_url(raw_endpoint: str) -> str:
    """Convert a Foundry project endpoint to the OpenAI-compatible base URL."""
    base = raw_endpoint.rstrip("/")
    if "/api/projects/" in base:
        resource_base = base.split("/api/projects/")[0]
        return f"{resource_base}/openai/v1"
    if base.endswith("/models"):
        return base.rsplit("/models", 1)[0] + "/openai/v1"
    if not base.endswith("/openai/v1"):
        return f"{base}/openai/v1"
    return base

# ==========================================
# 1. Configuration Setup
# ==========================================
# The evaluators need to know which LLM to use as the "Judge"
model_config = {
    "type": "openai",
    "api_key": os.getenv("FOUNDRY_API_KEY"),
    "model": os.getenv("FOUNDRY_DEPLOYMENT", "gpt-4o"),
    "base_url": get_base_url(os.getenv("FOUNDRY_ENDPOINT", "")),
}

# Initialize the Evaluators
print("Initializing AI Evaluators...")
groundedness_eval = GroundednessEvaluator(model_config=model_config)
relevance_eval = RelevanceEvaluator(model_config=model_config)

# ==========================================
# 2. Mock RAG Data (The Test Dataset)
# ==========================================
# In a real scenario, this data is exported from your app's logs.
qa_pairs = [
    {
        "scenario": "Perfect RAG Response",
        "query": "What is the policy on alcohol expenses?",
        "context": "Contoso Expense Policy: Meals can be expensed up to $75. Alcohol is strictly non-reimbursable.",
        "response": "According to the policy, alcohol is strictly non-reimbursable."
    },
    {
        "scenario": "Hallucinated Response (Not Grounded)",
        "query": "What is the policy on alcohol expenses?",
        "context": "Contoso Expense Policy: Meals can be expensed up to $75. Alcohol is strictly non-reimbursable.",
        "response": "You can expense alcohol up to $50 per day if you are with a client." # Hallucination!
    },
    {
        "scenario": "Irrelevant Response (Poor Retrieval)",
        "query": "How do I reset my password?",
        "context": "Contoso Expense Policy: Meals can be expensed up to $75. Alcohol is strictly non-reimbursable.",
        "response": "I cannot answer that based on the provided context." # Grounded, but irrelevant to the user's problem!
    }
]

# ==========================================
# 3. Execution Loop
# ==========================================
def run_evaluations():
    print("\nStarting Batch Evaluation...\n" + "="*50)
    
    for idx, test in enumerate(qa_pairs):
        print(f"Test {idx + 1}: {test['scenario']}")
        
        # 1. Measure Groundedness (Is the response supported by the context?)
        groundedness_result = groundedness_eval(
            query=test["query"],
            response=test["response"],
            context=test["context"]
        )
        
        # 2. Measure Relevance (Does the response answer the user's query?)
        relevance_result = relevance_eval(
            query=test["query"],
            response=test["response"],
            context=test["context"]
        )
        
        # 3. Print Results
        print(f"  Groundedness Score : {groundedness_result['groundedness']} / 5")
        print(f"  Relevance Score    : {relevance_result['relevance']} / 5")
        print("-" * 50)

if __name__ == "__main__":
    run_evaluations()
