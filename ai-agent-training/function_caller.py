import os
import json
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

api_key = os.getenv("FOUNDRY_API_KEY")
base_url = get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))
deployment_name = os.getenv("FOUNDRY_DEPLOYMENT", "gpt-4o")

client = OpenAI(api_key=api_key, base_url=base_url)

# 1. The Local Python Function
def get_stock_price(ticker_symbol: str) -> str:
    """Mock API call to get the current stock price."""
    print(f"  [System] Executing local API call for ticker: {ticker_symbol}...")

    mock_db = {
        "MSFT": {"price": 420.50, "currency": "USD"},
        "AAPL": {"price": 185.20, "currency": "USD"},
        "GOOGL": {"price": 140.10, "currency": "USD"}
    }

    ticker = ticker_symbol.upper()
    if ticker in mock_db:
        return json.dumps(mock_db[ticker])
    else:
        return json.dumps({"error": "Ticker not found. Suggest checking major tech stocks."})
# 2. The Tool Schema for the LLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current stock price for a given ticker symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker_symbol": {
                        "type": "string",
                        "description": "The stock ticker symbol, e.g., MSFT, AAPL",
                    }
                },
                "required": ["ticker_symbol"],
            },
        }
    }
]

# 3. The Execution Loop
def run_financial_agent(user_query: str):
    print(f"\nUser: {user_query}")

    messages = [
        {"role": "system", "content": "You are a helpful financial assistant. Use the supplied tools to answer questions."},
        {"role": "user", "content": user_query}
    ]

    # Step 1: Send the conversation and available tools to the model
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=tools,
        tool_choice="auto"  # Let the model decide if it needs to use a tool
    )

    response_message = response.choices[0].message

    # Step 2: Check if the model decided to call a tool
    if response_message.tool_calls:
        print("  [Agent] decided to use a tool. Pausing text generation...")

        # We must append the model's tool request to the conversation history
        messages.append(response_message)

        # Step 3: Execute the local function for every requested tool
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "get_stock_price":
                # Parse the JSON arguments provided by the LLM
                function_args = json.loads(tool_call.function.arguments)

                # Execute our local Python code
                function_response = get_stock_price(ticker_symbol=function_args.get("ticker_symbol"))

                # Step 4: Append the real-world result back into the message history
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": function_response,
                })

        # Step 5: Send the updated history back to the model so it can generate a final answer
        print("  [System] Tool results received. Generating final response...")
        final_response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
        )
        print(f"\nAgent: {final_response.choices[0].message.content}")

    else:
        # The model answered the question without needing a tool
        print(f"\nAgent: {response_message.content}")

if __name__ == "__main__":
    run_financial_agent("What is the current stock price of Microsoft?")
