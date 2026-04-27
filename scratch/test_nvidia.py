import litellm
import os
import sys

api_key = "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"
model = "openai/abacusai/dracarys-llama-3.1-70b-instruct"
base_url = "https://integrate.api.nvidia.com/v1"

print(f"Testing NVIDIA NIM: {model}")

try:
    response = litellm.completion(
        model=model, 
        messages=[{"role": "user", "content": "hi"}],
        api_key=api_key,
        base_url=base_url,
        timeout=15
    )
    print(f"✅ Success with NVIDIA NIM!")
    print(f"Response: {response.choices[0].message.content}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {type(e).__name__} - {str(e)}")
    sys.exit(1)
