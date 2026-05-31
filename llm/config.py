import os
import litellm
from dotenv import load_dotenv
from crewai import LLM

# Monkey-patch GeminiCompletion and litellm.completion to solve safety_settings mismatch.
# GeminiCompletion validates safety_settings to be a dict, but Gemini API via LiteLLM expects a list.
try:
    from crewai.llms.providers.gemini.completion import GeminiCompletion
    
    _orig_prepare_generation_config = GeminiCompletion._prepare_generation_config
    
    def _patched_prepare_generation_config(self, *args, **kwargs):
        original_settings = self.safety_settings
        if isinstance(original_settings, dict):
            self.safety_settings = [
                {"category": cat, "threshold": thresh}
                for cat, thresh in original_settings.items()
            ]
        try:
            return _orig_prepare_generation_config(self, *args, **kwargs)
        finally:
            self.safety_settings = original_settings

    GeminiCompletion._prepare_generation_config = _patched_prepare_generation_config
    import logging
    logging.getLogger("terraform-dashboard").info("Successfully monkey-patched GeminiCompletion._prepare_generation_config")
except Exception as e:
    import logging
    logging.getLogger("terraform-dashboard").warning(f"Failed to monkey-patch GeminiCompletion: {e}")

# Monkey-patch litellm.completion to convert safety_settings and handle automatic OpenRouter free fallback on rate limit/quota errors.
_orig_litellm_completion = litellm.completion

def _patched_litellm_completion(*args, **kwargs):
    if "safety_settings" in kwargs and isinstance(kwargs["safety_settings"], dict):
        kwargs["safety_settings"] = [
            {"category": cat, "threshold": thresh}
            for cat, thresh in kwargs["safety_settings"].items()
        ]
    try:
        return _orig_litellm_completion(*args, **kwargs)
    except Exception as e:
        error_str = str(e).lower()
        is_quota_error = any(kw in error_str for kw in ["quota", "rate", "limit", "429", "exhausted", "credits", "402", "502", "stealth", "venice"])
        if is_quota_error:
            import time
            import logging
            # 1. Retry the primary model with backoff first
            max_primary_retries = 3
            primary_retry_delay = 5
            for attempt in range(max_primary_retries):
                logging.getLogger("terraform-dashboard").warning(
                    f"[LiteLLM Retry] Primary call rate-limited/quota error. Retrying original model {kwargs.get('model')} in {primary_retry_delay}s (Attempt {attempt+1}/{max_primary_retries})..."
                )
                time.sleep(primary_retry_delay)
                try:
                    return _orig_litellm_completion(*args, **kwargs)
                except Exception as retry_err:
                    retry_error_str = str(retry_err).lower()
                    if not any(kw in retry_error_str for kw in ["quota", "rate", "limit", "429", "exhausted", "credits", "402", "502", "stealth", "venice"]):
                        raise retry_err
                    primary_retry_delay *= 2
            
            # 2. If primary model retries failed, proceed with fallback candidates
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                fallback_kwargs = kwargs.copy()
                fallback_kwargs["api_key"] = openrouter_key
                fallback_kwargs.pop("safety_settings", None)
                os.environ["OPENROUTER_API_KEY"] = openrouter_key
                
                # Multi-stage fallback candidate models for LiteLLM (prefixed with openrouter/)
                candidate_models = [
                    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                    "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
                    "openrouter/google/gemma-4-31b-it:free",
                    "openrouter/deepseek/deepseek-v4-flash:free"
                ]
                
                last_err = e
                for model in candidate_models:
                    if model in fallback_kwargs.get("model", ""):
                        continue
                    logging.getLogger("terraform-dashboard").warning(
                        f"[LiteLLM Fallback] Primary call failed ({e}). Cooling down 3s then trying model: {model}..."
                    )
                    time.sleep(3)  # Prevent cascading 429s across fallback models
                    fallback_kwargs["model"] = model
                    try:
                        return _orig_litellm_completion(*args, **fallback_kwargs)
                    except Exception as fallback_err:
                        logging.getLogger("terraform-dashboard").warning(
                            f"[LiteLLM Fallback] Model {model} failed: {fallback_err}"
                        )
                        last_err = fallback_err
                raise last_err
        raise e

litellm.completion = _patched_litellm_completion

# Monkey-patch openai's sync completion to handle OpenRouter rate limits / transient errors.
try:
    import openai
    _orig_openai_chat_create = openai.resources.chat.completions.Completions.create
    
    def _patched_openai_chat_create(self, *args, **kwargs):
        try:
            return _orig_openai_chat_create(self, *args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            is_transient_error = any(kw in error_str for kw in [
                "quota", "rate", "limit", "429", "exhausted", "credits", "402", "502", "stealth", "venice"
            ])
            if is_transient_error:
                import time
                import logging
                
                # 1. Retry the primary model with backoff first
                max_primary_retries = 3
                primary_retry_delay = 5
                for attempt in range(max_primary_retries):
                    logging.getLogger("terraform-dashboard").warning(
                        f"[OpenAI Retry] Primary call rate-limited/quota error. Retrying original model {kwargs.get('model')} in {primary_retry_delay}s (Attempt {attempt+1}/{max_primary_retries})...."
                    )
                    time.sleep(primary_retry_delay)
                    try:
                        return _orig_openai_chat_create(self, *args, **kwargs)
                    except Exception as retry_err:
                        retry_error_str = str(retry_err).lower()
                        if not any(kw in retry_error_str for kw in ["quota", "rate", "limit", "429", "exhausted", "credits", "402", "502", "stealth", "venice"]):
                            raise retry_err
                        primary_retry_delay *= 2

                # 2. If primary model retries failed, proceed with fallback candidates
                openrouter_key = os.getenv("OPENROUTER_API_KEY")
                if openrouter_key:
                    fallback_kwargs = kwargs.copy()
                    
                    # Ensure base_url and api_key are pointing to OpenRouter
                    self.base_url = "https://openrouter.ai/api/v1"
                    self.api_key = openrouter_key
                    if "api_key" in fallback_kwargs:
                        fallback_kwargs["api_key"] = openrouter_key
                    fallback_kwargs.pop("safety_settings", None)
                    
                    # Multi-stage fallback candidate models for OpenAI (non-prefixed or raw OpenRouter names)
                    candidate_models = [
                        "meta-llama/llama-3.3-70b-instruct:free",
                        "qwen/qwen3-next-80b-a3b-instruct:free",
                        "google/gemma-4-31b-it:free",
                        "deepseek/deepseek-v4-flash:free"
                    ]
                    
                    last_err = e
                    for model in candidate_models:
                        if model in fallback_kwargs.get("model", ""):
                            continue
                        logging.getLogger("terraform-dashboard").warning(
                            f"[OpenAI Fallback] Primary call failed ({e}). Cooling down 3s then trying model: {model}..."
                        )
                        time.sleep(3)  # Prevent cascading 429s across fallback models
                        fallback_kwargs["model"] = model
                        try:
                            return _orig_openai_chat_create(self, *args, **fallback_kwargs)
                        except Exception as fallback_err:
                            logging.getLogger("terraform-dashboard").warning(
                                f"[OpenAI Fallback] Model {model} failed: {fallback_err}"
                            )
                            last_err = fallback_err
                    raise last_err
            raise e

    openai.resources.chat.completions.Completions.create = _patched_openai_chat_create
    import logging
    logging.getLogger("terraform-dashboard").info("Successfully monkey-patched openai.Completions.create")
except Exception as patch_err:
    import logging
    logging.getLogger("terraform-dashboard").warning(f"Failed to monkey-patch openai.Completions.create: {patch_err}")

# Load environment variables
load_dotenv()

# Force LiteLLM to stay out of Vertex AI mode
os.environ["LITELLM_LOG"] = "DEBUG"
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

# ─── Rate Limit / Retry Settings ───
# LiteLLM will automatically wait & retry on 429 with exponential backoff
litellm.set_verbose = True
litellm.num_retries = 10               # Increased to wait out free tier rate limits
litellm.request_timeout = 120          # 2 min timeout per request
litellm.retry_after = 5                # Min 5s wait between retries

def get_llm(model_name=None, api_key=None):
    """
    Returns a CrewAI LLM instance.
    Detects the provider (gemini, groq, openai) from model name prefix.
    """
    if not model_name:
        model_name = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
    
    # Map generic/unstable OpenRouter free router to a stable specific free model
    if model_name in ["openrouter/free", "openrouter/openrouter/free", "free", "openrouter/"]:
        model_name = "openrouter/meta-llama/llama-3.3-70b-instruct:free"
    
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
            "openrouter": os.getenv("OPENROUTER_API_KEY"),
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
                "chat_template_kwargs": {"thinking": False}
            }
    elif provider == "openrouter":
        os.environ["OPENROUTER_API_KEY"] = api_key
    elif provider in ["gemini", "google_ai"]:

        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
        # For litellm with API Key, use gemini/ prefix
        model_part = model_name.split("/")[-1]
        model_name = f"gemini/{model_part}"
        
        # Disable all safety blocks to prevent false positive empty responses
        extra_kwargs["safety_settings"] = {
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
        }

    if not api_key:
        print(f"Warning: No API key found for provider '{provider}'.")

    llm_params = {
        "model": model_name,
        "temperature": 0.7,
        "api_key": api_key,
        "timeout": 300,
        **extra_kwargs
    }
    
    if provider not in ["openai", "openrouter"]:
        llm_params["num_retries"] = 5

    return LLM(**llm_params)


