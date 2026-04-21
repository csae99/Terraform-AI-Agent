import os
from dotenv import load_dotenv
from crewai import LLM

# Load environment variables
load_dotenv()

# Force LiteLLM to stay out of Vertex AI mode
os.environ["LITELLM_LOGGING"] = "DEBUG"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

def get_llm():
    """
    Returns a CrewAI LLM instance.
    Detects the provider (gemini, groq, openai) from DEFAULT_MODEL prefix.
    """
    model_name = os.getenv("DEFAULT_MODEL", "gemini/gemini-flash-latest")
    
    # Default to gemini if no prefix is provided
    if "/" not in model_name:
        model_name = f"gemini/{model_name}"
    
    provider = model_name.split("/")[0].lower()
    
    # Map provider to the correct API key from environment
    key_map = {
        "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        "google_ai": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        "groq": os.getenv("GROQ_API_KEY"),
        "mistral": os.getenv("MISTRAL_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
    }
    
    api_key = key_map.get(provider)
    
    if not api_key:
        print(f"Warning: No API key found for provider '{provider}'.")

    return LLM(
        model=model_name,
        temperature=0.7,
        api_key=api_key
    )
