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
    Returns a CrewAI LLM instance configured for the Gemini API.
    Using 'google_ai/' prefix is the most explicit way in LiteLLM 1.74+
    to target the Gemini API (AI Studio) and avoid Vertex AI misrouting.
    """
    model_name = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
    if "/" in model_name:
        model_name = model_name.split("/")[-1]
    
    # Official LiteLLM prefix for Gemini API (not Vertex)
    full_model_path = f"google_ai/{model_name}"
    
    return LLM(
        model=full_model_path,
        temperature=0.7,
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
