import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatLiteLLM

# Load environment variables
load_dotenv()

def get_llm():
    """
    Returns a ChatLiteLLM instance configured with the DEFAULT_MODEL 
    from the .env file. This enables seamless routing to OpenAI, Anthropic, 
    Groq, Gemini, or local models via Ollama.
    """
    model = os.getenv("DEFAULT_MODEL", "openai/gpt-3.5-turbo")
    
    # We use LangChain's ChatLiteLLM wrapper which allows CrewAI 
    # to communicate natively with LiteLLM's routing engine.
    llm = ChatLiteLLM(
        model=model,
        temperature=0.7,
        # API keys are automatically picked up by litellm from the environment rules
    )
    return llm
