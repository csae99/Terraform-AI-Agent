import os
from dotenv import load_dotenv
from crewai import LLM

# Load environment variables
load_dotenv()

# Force LiteLLM to stay out of Vertex AI mode
os.environ["LITELLM_LOGGING"] = "DEBUG"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

def get_llm(model_name=None, api_key=None):
    """
    Returns a CrewAI LLM instance.
    Detects the provider (gemini, groq, openai) from model name prefix.
    """
    if not model_name:
        model_name = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
    
    # Handle common prefixes
    if "/" not in model_name:
        if model_name.startswith("gpt"):
            model_name = f"openai/{model_name}"
        elif model_name.startswith("claude"):
            model_name = f"anthropic/{model_name}"
        elif model_name.startswith("gemini"):
            model_name = f"gemini/{model_name}"
    
    # Provider detection & normalization
    extra_kwargs = {}
    if "/" in model_name:
        provider = model_name.split("/")[0].lower()
    elif model_name.startswith("gpt"):
        provider = "openai"
    elif model_name.startswith("claude"):
        provider = "anthropic"
    else:
        provider = "gemini"

    # Use provided key or map from environment
    if not api_key:
        key_map = {
            "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            "google_ai": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            "groq": os.getenv("GROQ_API_KEY"),
            "mistral": os.getenv("MISTRAL_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "nvidia": os.getenv("NVIDIA_API_KEY"),
        }
        api_key = key_map.get(provider)

    if provider == "nvidia":
        # Map nvidia/ prefix to openai/ compatible with NVIDIA NIM base_url
        model_part = model_name.split("/", 1)[1]
        model_name = f"openai/{model_part}"
        extra_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
        os.environ["OPENAI_API_KEY"] = api_key # LiteLLM uses this for base_url providers
        
        # Add thinking support for DeepSeek models
        if "deepseek" in model_part.lower():
            extra_kwargs["extra_body"] = {
                "chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}
            }
    elif provider in ["gemini", "google_ai"]:

        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
        # For litellm with API Key, use gemini/ prefix
        model_part = model_name.split("/")[-1]
        model_name = f"gemini/{model_part}"

    if not api_key:
        print(f"Warning: No API key found for provider '{provider}'.")

    return LLM(
        model=model_name,
        temperature=0.7,
        api_key=api_key,
        **extra_kwargs
    )


