import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from openai import OpenAI

load_dotenv()

class UserProfile(BaseModel):
    name: str
    age: int
    skills: list[str]
    is_active_employee: bool

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

print("Schema defined successfully. Ready to validate data.")

def extract_profile_data(messy_text):
    api_key = os.getenv("FOUNDRY_API_KEY")
    base_url = get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))
    
    # Ensure this matches your deployment name in AI Foundry
    deployment_name = "gpt-4o" 
    
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    system_prompt = """
    You are a data extraction agent. Your job is to extract user information from messy text.
    You MUST respond with a raw, valid JSON object and absolutely nothing else.
    Do not use markdown code blocks like ```json. 
    
    The JSON object must have exactly these keys:
    - "name": string
    - "age": integer
    - "skills": array of strings
    - "is_active_employee": boolean
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": messy_text}
    ]

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=0.0
        )
        raw_output = response.choices[0].message.content.strip()
        
        # Clean up any rogue markdown formatting if the LLM disobeys the prompt
        if raw_output.startswith("```json"):
            raw_output = raw_output[7:]
        if raw_output.endswith("```"):
            raw_output = raw_output[:-3]
            
        return raw_output.strip()

    except Exception as e:
        print(f"API Error: {e}")
        return None

if __name__ == "__main__":
    test_text = (
        "Hey there! So we just interviewed Johnathan Doe. He's 34 years old and "
        "seems like a great fit. He previously worked with Python, Kubernetes, and AWS. "
        "We haven't officially hired him yet, so he is not currently on the payroll."
    )
    
    print("\n--- Extracting Data ---")
    raw_json_string = extract_profile_data(test_text)
    print(f"Raw LLM Output:\n{raw_json_string}\n")
    
    print("--- Validating with Pydantic ---")
    try:
        parsed_dict = json.loads(raw_json_string)
        
        validated_profile = UserProfile(**parsed_dict)
        
        print("Success! Data successfully mapped to Python object:")
        print(f"Name:  {validated_profile.name}")
        print(f"Age:   {validated_profile.age}")
        print(f"Skills: {validated_profile.skills}")
        print(f"Active: {validated_profile.is_active_employee}")
        
    except json.JSONDecodeError:
        print("CRITICAL FAILURE: The LLM did not return valid JSON syntax.")
    except ValidationError as e:
        print(f"SCHEMA FAILURE: The LLM returned JSON, but it didn't match the required schema.\nDetails: {e}")
