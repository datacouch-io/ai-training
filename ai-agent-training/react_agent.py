import os
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ==========================================
# 1. Define Local Tools
# ==========================================
def calculate(expression: str) -> str:
    """A simple calculator tool using Python's eval."""
    try:
        # In production, NEVER use raw eval() on LLM output without strict sanitization.
        # We use it here strictly for educational sandbox purposes.
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error calculating: {e}"

def get_weather(location: str) -> str:
    """A mock API to fetch weather data."""
    mock_db = {
        "london": "Rainy, 10°C",
        "dubai": "Sunny, 35°C",
        "tokyo": "Cloudy, 18°C"
    }
    return mock_db.get(location.lower().strip(), "Weather data not available for this location.")

# Map tool names to their actual Python functions
AVAILABLE_TOOLS = {
    "calculate": calculate,
    "get_weather": get_weather
}

# ==========================================
# 2. Azure AI Foundry Client Setup
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
deployment_name = "gpt-4o" # Ensure this matches your deployment name

client = OpenAI(api_key=api_key, base_url=base_url)

# ==========================================
# 3. The ReAct System Prompt
# ==========================================
SYSTEM_PROMPT = """
You are a logical AI agent that solves problems by using tools.
You have access to the following tools:
- calculate: Evaluates a mathematical expression. Input should be a math string (e.g., 25 * 4).
- get_weather: Gets the current weather. Input should be a city name (e.g., London).

You must solve the user's request by following this EXACT format:
Thought: Think about what you need to do next.
Action: The name of the tool to use (must be 'calculate' or 'get_weather').
Action Input: The input payload for the tool.

(Wait for the user to provide an Observation)

When you have the final answer to the original request, you must use this format:
Thought: I now have the final answer.
Final Answer: [Your actual answer to the user]
"""

# ==========================================
# 4. The Execution Loop
# ==========================================
def run_agent(user_query: str, max_iterations: int = 5):
    print(f"\n[User Query]: {user_query}\n")
    print("-" * 50)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]
    
    # Regex patterns to extract the Action and Action Input from the LLM's text
    action_pattern = re.compile(r"Action:\s*(.*)")
    input_pattern = re.compile(r"Action Input:\s*(.*)")
    
    for i in range(max_iterations):
        # 1. Ask the LLM to generate its next Thought and Action
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=0.0 # Determinism is critical for formatted output
        )
        
        llm_text = response.choices[0].message.content.strip()
        print(f"[Agent]:\n{llm_text}\n")
        
        # Add the LLM's response to the conversation history
        messages.append({"role": "assistant", "content": llm_text})
        
        # 2. Check if the agent has reached a Final Answer
        if "Final Answer:" in llm_text:
            print("\n[Agent Finished Successfully]")
            return
            
        # 3. If no final answer, parse the Action to execute tools
        action_match = action_pattern.search(llm_text)
        input_match = input_pattern.search(llm_text)
        
        if action_match and input_match:
            tool_name = action_match.group(1).strip()
            tool_input = input_match.group(1).strip()
            
            print(f">>> Executing Tool: [{tool_name}] with input: [{tool_input}]")
            
            # Execute the local Python function
            if tool_name in AVAILABLE_TOOLS:
                observation = AVAILABLE_TOOLS[tool_name](tool_input)
            else:
                observation = f"Error: Tool '{tool_name}' does not exist."
                
            print(f">>> Observation: {observation}\n")
            print("-" * 50)
            
            # 4. Provide the Observation back to the LLM so it can continue reasoning
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            
        else:
            # The LLM failed to follow the formatting instructions
            error_msg = "Observation: Format error. You must provide an Action and Action Input."
            print(f">>> {error_msg}\n")
            messages.append({"role": "user", "content": error_msg})

    print("\n[Agent Terminated: Max iterations reached without a Final Answer]")

if __name__ == "__main__":
    # Test a complex prompt requiring two separate tools
    complex_query = "What is the weather like in Dubai? If I buy 3 shirts there for $24 each, what is my total cost?"
    run_agent(complex_query)
