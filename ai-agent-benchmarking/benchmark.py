import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


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


def run_benchmark(client, model_deployment_name, prompt):
    print(f"--- Initiating benchmark for: {model_deployment_name} ---")

    messages = [
        {"role": "system", "content": "You are a strict, logical planning agent. Respond concisely."},
        {"role": "user", "content": prompt},
    ]

    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=model_deployment_name,
            messages=messages,
        )
        end_time = time.time()

        latency = end_time - start_time
        completion_text = response.choices[0].message.content
        usage = response.usage

        print(f"Latency       : {latency:.2f} seconds")
        print(f"Prompt Tokens : {usage.prompt_tokens}")
        print(f"Completion Tk : {usage.completion_tokens}")
        print(f"Total Tokens  : {usage.total_tokens}")
        print(f"Response      : {completion_text[:100]}...\n")

    except Exception as e:
        print(f"Error during API call to {model_deployment_name}: {e}\n")


if __name__ == "__main__":
    deployment_a = "gpt-4o"
    deployment_b = "Phi-4-mini-instruct"

    test_prompt = (
        "Extract the entities from the following text and format them as a JSON array: "
        "'Microsoft announced a new datacenter in Madrid, Spain, scheduled for completion by 2026. "
        "Satya Nadella emphasized the importance of sustainable AI infrastructure.'"
    )

    api_key = os.getenv("FOUNDRY_API_KEY")
    base_url = get_base_url(os.getenv("FOUNDRY_ENDPOINT", ""))

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    print("Starting Multi-Provider Benchmarking...\n")

    run_benchmark(client, deployment_a, test_prompt)
    run_benchmark(client, deployment_b, test_prompt)
