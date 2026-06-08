import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_base_url(raw_endpoint: str) -> str:
    base = raw_endpoint.rstrip("/")
    if "/api/projects/" in base:
        if base.endswith("/openai/v1"):
            return base
        return f"{base}/openai/v1"
    if base.endswith("/models"):
        return base.rsplit("/models", 1)[0] + "/openai/v1"
    if not base.endswith("/openai/v1"):
        return f"{base}/openai/v1"
    return base

def route_ticket_llm(ticket_text):
    api_key = os.getenv("FOUNDRY_API_KEY")
    base_url = get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))
    
    # Ensure this matches your deployment name in AI Foundry
    deployment_name = "gpt-4o" 
    
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    system_prompt = """
    You are an intelligent routing agent for a software company.
    Analyze the customer's request and categorize it into EXACTLY ONE of the following departments:
    - Billing
    - Technical Support
    - Sales
    - Uncategorized
    
    Respond with ONLY the name of the department. Do not include any other text or punctuation.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": ticket_text}
    ]

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    test_tickets = [
        "I was charged twice for my subscription this month.",
        "How much does it cost to upgrade to the enterprise plan?",
        "My app keeps crashing when I try to upload a photo.",
        "I am so mad! The new laptop I just bought has a broken screen, I want a refund right now!"
    ]
    
    print("--- LLM-Driven AI Agent Routing ---")
    for idx, ticket in enumerate(test_tickets):
        category = route_ticket_llm(ticket)
        print(f"Ticket {idx + 1}: {category} | Text: '{ticket}'")
