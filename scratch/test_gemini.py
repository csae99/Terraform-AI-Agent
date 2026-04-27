import litellm
import os
import sys

api_key = "AIzaSyDC_1itEKLk0oSyE0nJcp5turTRgl7xPss"
os.environ["GEMINI_API_KEY"] = api_key
os.environ["GOOGLE_API_KEY"] = api_key

# Force pop Vertex/GC variables
gc_vars = [
    "GOOGLE_APPLICATION_CREDENTIALS", 
    "GOOGLE_CLOUD_PROJECT",
    "GCLOUD_PROJECT",
    "GOOGLE_CLOUD_REGION",
    "CLOUD_SDK_CONFIG",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY"
]
for v in gc_vars:
    os.environ.pop(v, None)

api_key = "AIzaSyDC_1itEKLk0oSyE0nJcp5turTRgl7xPss"
os.environ["GEMINI_API_KEY"] = api_key
os.environ["GOOGLE_API_KEY"] = api_key

print("Testing Gemini via LiteLLM...")

models_to_try = [
    ("gemini/gemini-1.5-flash", None),
    ("gemini/gemini-1.5-flash", "google_ai"),
    ("gemini/gemini-1.5-flash", "gemini"),
    ("gemini-1.5-flash", "google_ai"),
    ("gemini-1.5-flash", "gemini"),
    ("google_ai/gemini-1.5-flash", None),
    ("models/gemini-1.5-flash", "google_ai")
]

print(f"\n--- Trying Gemini OpenAI-Compatible Endpoint ---")
try:
    response = litellm.completion(
        model="openai/gemini-1.5-flash", 
        messages=[{"role": "user", "content": "hi"}],
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=10
    )
    print(f"✅ Success with OpenAI-compatible endpoint!")
    print(f"Response: {response.choices[0].message.content}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {type(e).__name__} - {str(e)}")

print("\nAll attempts failed.")
sys.exit(1)

