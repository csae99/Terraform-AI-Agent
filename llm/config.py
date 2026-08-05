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
_last_gemini_call_time = 0.0  # Module-level tracker for Gemini free-tier throttling

def _patched_litellm_completion(*args, **kwargs):
    model_name = kwargs.get("model")
    is_gemini = False
    if model_name and isinstance(model_name, str):
        is_gemini = "gemini" in model_name.lower() or "google_ai" in model_name.lower() or "google/" in model_name.lower()
        
    if is_gemini and os.getenv("GEMINI_FREE_TIER_THROTTLE", "true").lower() == "true":
        import time
        global _last_gemini_call_time
        
        now = time.time()
        elapsed = now - _last_gemini_call_time
        # 15 RPM = 1 call every 4.0 seconds. 4.2 seconds is safe.
        if elapsed < 4.2:
            sleep_time = 4.2 - elapsed
            import logging
            logging.getLogger("terraform-dashboard").info(
                f"[Rate Limiter] Throttling Gemini API call by {sleep_time:.2f}s to respect 15 RPM free tier limit..."
            )
            time.sleep(sleep_time)
        _last_gemini_call_time = time.time()

    if model_name and isinstance(model_name, str):
        # Intercept and route openai/gpt-oss-120b to groq/openai/gpt-oss-120b or openrouter/openai/gpt-oss-120b
        if "gpt-oss-120b" in model_name.lower():
            groq_key = kwargs.get("api_key") or os.getenv("GROQ_API_KEY")
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if groq_key and str(groq_key).startswith("gsk_"):
                if not model_name.startswith("groq/"):
                    if model_name.startswith("openai/"):
                        model_name = f"groq/{model_name}"
                    else:
                        model_name = f"groq/openai/{model_name.split('/')[-1]}"
                kwargs["model"] = model_name
                kwargs["api_key"] = groq_key
                os.environ["GROQ_API_KEY"] = groq_key
            elif openrouter_key:
                if not model_name.startswith("openrouter/"):
                    if model_name.startswith("openai/"):
                        model_name = f"openrouter/{model_name}"
                    else:
                        model_name = f"openrouter/openai/{model_name.split('/')[-1]}"
                kwargs["model"] = model_name
                kwargs["api_key"] = openrouter_key
                os.environ["OPENROUTER_API_KEY"] = openrouter_key

        provider = None
        if "/" in model_name:
            provider = model_name.split("/")[0].lower()
            
        if provider == "nvidia":
            model_part = model_name.split("/", 1)[1]
            kwargs["model"] = f"openai/{model_part}"
            kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
            if "api_key" not in kwargs or not kwargs["api_key"]:
                nvidia_key = os.getenv("NVIDIA_API_KEY")
                if nvidia_key:
                    kwargs["api_key"] = nvidia_key
                    os.environ["OPENAI_API_KEY"] = nvidia_key
            if "deepseek" in model_part.lower():
                if "extra_body" not in kwargs:
                    kwargs["extra_body"] = {}
                if "chat_template_kwargs" not in kwargs["extra_body"]:
                    kwargs["extra_body"]["chat_template_kwargs"] = {}
                kwargs["extra_body"]["chat_template_kwargs"]["thinking"] = False

        elif provider in ("zenmux", "z-ai", "moonshotai"):
            # ZenMux AI - OpenAI-compatible at https://zenmux.ai/api/v1
            # Models arrive as zenmux/model, z-ai/model, or moonshotai/model
            if provider == "zenmux":
                model_part = model_name.split("/", 1)[1]  # e.g. "z-ai/glm-4.7-flash-free"
            else:
                model_part = model_name  # already "z-ai/glm-4.7-flash-free"
            kwargs["model"] = f"openai/{model_part}"
            kwargs["base_url"] = "https://zenmux.ai/api/v1"
            if "api_key" not in kwargs or not kwargs["api_key"]:
                zenmux_key = os.getenv("ZENMUX_API_KEY")
                if zenmux_key:
                    kwargs["api_key"] = zenmux_key

        elif provider == "openrouter":
            if "api_key" not in kwargs or not kwargs["api_key"]:
                openrouter_key = os.getenv("OPENROUTER_API_KEY")
                if openrouter_key:
                    kwargs["api_key"] = openrouter_key
                    os.environ["OPENROUTER_API_KEY"] = openrouter_key

        elif provider in ["gemini", "google_ai"]:
            if "api_key" not in kwargs or not kwargs["api_key"]:
                gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if gemini_key:
                    kwargs["api_key"] = gemini_key
                    os.environ["GEMINI_API_KEY"] = gemini_key
                    os.environ["GOOGLE_API_KEY"] = gemini_key
            model_part = model_name.split("/")[-1]
            kwargs["model"] = f"gemini/{model_part}"
            if "safety_settings" not in kwargs:
                kwargs["safety_settings"] = {
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
                }

    if "safety_settings" in kwargs and isinstance(kwargs["safety_settings"], dict):
        kwargs["safety_settings"] = [
            {"category": cat, "threshold": thresh}
            for cat, thresh in kwargs["safety_settings"].items()
        ]

    # Clean up prompt caching parameters for Mistral and Groq provider/models to avoid API rejection
    is_non_caching_provider = False
    if model_name and isinstance(model_name, str):
        model_lower = model_name.lower()
        is_non_caching_provider = (
            "mistral" in model_lower
            or "codestral" in model_lower
            or "pixtral" in model_lower
            or "groq" in model_lower
        )
    
    if is_non_caching_provider:
        messages = kwargs.get("messages")
        if messages and isinstance(messages, list):
            cleaned_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    msg_copy = msg.copy()
                    msg_copy.pop("cache_breakpoint", None)
                    msg_copy.pop("cache_control", None)
                    cleaned_messages.append(msg_copy)
                else:
                    cleaned_messages.append(msg)
            kwargs["messages"] = cleaned_messages

    def _execute_with_telemetry(params):
        res = _orig_litellm_completion(*args, **params)
        try:
            from litellm import completion_cost
            cost = completion_cost(res)
            if cost is None:
                cost = 0.0
            usage = getattr(res, "usage", None)
            prompt_t = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_t = getattr(usage, "completion_tokens", 0) if usage else 0
            import logging
            logging.getLogger("terraform-dashboard").info(
                f"[LLM Telemetry] Model: {params.get('model')} | "
                f"Prompt Tokens: {prompt_t} | Completion Tokens: {completion_t} | "
                f"Estimated Spend: ${cost:.6f}"
            )
        except Exception:
            pass
        return res

    try:
        return _execute_with_telemetry(kwargs)
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
                # Dynamically extract exact retryDelay or wait time from the Google/LiteLLM error message
                import re
                match_secs = re.search(r"retry\s+in\s+([\d\.]+)\s*s", error_str, re.IGNORECASE)
                match_delay = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", error_str, re.IGNORECASE)
                if match_secs:
                    primary_retry_delay = float(match_secs.group(1)) + 1.0
                elif match_delay:
                    primary_retry_delay = float(match_delay.group(1)) + 1.0
                
                logging.getLogger("terraform-dashboard").warning(
                    f"[LiteLLM Retry] Primary call rate-limited/quota error. Retrying original model {kwargs.get('model')} in {primary_retry_delay:.2f}s (Attempt {attempt+1}/{max_primary_retries})..."
                )
                time.sleep(primary_retry_delay)
                try:
                    return _execute_with_telemetry(kwargs)
                except Exception as retry_err:
                    retry_error_str = str(retry_err).lower()
                    if not any(kw in retry_error_str for kw in ["quota", "rate", "limit", "429", "exhausted", "credits", "402", "502", "stealth", "venice"]):
                        raise retry_err
                    # Re-parse from current error or do backoff
                    match_secs = re.search(r"retry\s+in\s+([\d\.]+)\s*s", retry_error_str, re.IGNORECASE)
                    match_delay = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", retry_error_str, re.IGNORECASE)
                    if match_secs:
                        primary_retry_delay = float(match_secs.group(1)) + 1.0
                    elif match_delay:
                        primary_retry_delay = float(match_delay.group(1)) + 1.0
                    else:
                        primary_retry_delay *= 2
            
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                fallback_kwargs = kwargs.copy()
                fallback_kwargs["api_key"] = openrouter_key
                fallback_kwargs.pop("safety_settings", None)
                fallback_kwargs.pop("base_url", None)  # Remove ZenMux/NVIDIA base_url overrides
                os.environ["OPENROUTER_API_KEY"] = openrouter_key
                
                # Multi-stage fallback candidate models for LiteLLM (prefixed with openrouter/)
                candidate_models = [
                    "openrouter/poolside/laguna-xs-2.1:free",
                    "openrouter/tencent/hy3:free",
                    "openrouter/cohere/north-mini-code:free"
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
                        return _execute_with_telemetry(fallback_kwargs)
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
        model = kwargs.get("model")
        is_groq = False
        if model and "gpt-oss-120b" in model.lower():
            # If the user passed gpt-oss-120b but configured their groq API key, route to Groq base_url
            groq_key = getattr(self, "api_key", None) or os.getenv("GROQ_API_KEY")
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            import httpx
            if groq_key and str(groq_key).startswith("gsk_"):
                self._client.base_url = httpx.URL("https://api.groq.com/openai/v1")
                self._client.api_key = groq_key
                is_groq = True
            elif openrouter_key:
                self._client.base_url = httpx.URL("https://openrouter.ai/api/v1")
                self._client.api_key = openrouter_key
        
        # Strip prompt caching parameters if routing to Groq or Mistral
        is_non_caching_provider = is_groq or (model and ("groq" in model.lower() or "mistral" in model.lower() or "codestral" in model.lower() or "pixtral" in model.lower()))
        if is_non_caching_provider:
            messages = kwargs.get("messages")
            if messages and isinstance(messages, list):
                cleaned_messages = []
                for msg in messages:
                    if isinstance(msg, dict):
                        msg_copy = msg.copy()
                        msg_copy.pop("cache_breakpoint", None)
                        msg_copy.pop("cache_control", None)
                        cleaned_messages.append(msg_copy)
                    else:
                        cleaned_messages.append(msg)
                kwargs["messages"] = cleaned_messages
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
                    orig_base_url = getattr(self._client, "base_url", None)
                    orig_api_key = getattr(self._client, "api_key", None)
                    try:
                        # Ensure base_url and api_key are pointing to OpenRouter
                        import httpx
                        self._client.base_url = httpx.URL("https://openrouter.ai/api/v1")
                        self._client.api_key = openrouter_key
                        if "api_key" in fallback_kwargs:
                            fallback_kwargs["api_key"] = openrouter_key
                        fallback_kwargs.pop("safety_settings", None)
                        
                        # Multi-stage fallback candidate models for OpenAI (non-prefixed or raw OpenRouter names)
                        candidate_models = [
                            "poolside/laguna-xs-2.1:free",
                            "tencent/hy3:free",
                            "cohere/north-mini-code:free"
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
                    finally:
                        if orig_base_url is not None:
                            self._client.base_url = orig_base_url
                        if orig_api_key is not None:
                            self._client.api_key = orig_api_key
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
        model_name = os.getenv("DEFAULT_MODEL", "zenmux/moonshotai/kimi-k3-free")
    
    # Map generic/unstable OpenRouter free router to a stable specific free model
    if model_name in ["openrouter/free", "openrouter/openrouter/free", "free", "openrouter/"]:
        model_name = "openrouter/poolside/laguna-xs-2.1:free"

    # Route openai/gpt-oss-120b to groq/openai/gpt-oss-120b or openrouter/openai/gpt-oss-120b
    if model_name and "gpt-oss-120b" in model_name.lower():
        # Prefer provided api_key if it is a groq key, otherwise env vars
        groq_key = api_key if (api_key and str(api_key).startswith("gsk_")) else os.getenv("GROQ_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if groq_key:
            if not model_name.startswith("groq/"):
                if model_name.startswith("openai/"):
                    model_name = f"groq/{model_name}"
                else:
                    model_name = f"groq/openai/{model_name.split('/')[-1]}"
            api_key = groq_key
        elif openrouter_key:
            if not model_name.startswith("openrouter/"):
                if model_name.startswith("openai/"):
                    model_name = f"openrouter/{model_name}"
                else:
                    model_name = f"openrouter/openai/{model_name.split('/')[-1]}"
            api_key = openrouter_key
    
    # Handle common prefixes
    if model_name.startswith("z-ai/") or model_name.startswith("z-ai"):
        model_name = f"zenmux/{model_name}"
    elif model_name.startswith("moonshotai/"):
        model_name = f"zenmux/{model_name}"

    if "//" not in model_name and "/" not in model_name:
        if model_name.startswith("gpt"):
            model_name = f"openai/{model_name}"
        elif model_name.startswith("claude"):
            model_name = f"anthropic/{model_name}"
        elif model_name.startswith("gemini") or model_name.startswith("gemma"):
            model_name = f"gemini/{model_name}"
        elif model_name.startswith("mistral") or model_name.startswith("codestral") or model_name.startswith("pixtral"):
            model_name = f"mistral/{model_name}"
    
    # Provider detection & normalization
    extra_kwargs = {}
    if "/" in model_name:
        provider = model_name.split("/")[0].lower()
    elif model_name.startswith("gpt"):
        provider = "openai"
    elif model_name.startswith("claude"):
        provider = "anthropic"
    elif model_name.startswith("mistral") or model_name.startswith("codestral") or model_name.startswith("pixtral"):
        provider = "mistral"
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
            "zenmux": os.getenv("ZENMUX_API_KEY"),
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
    elif provider == "zenmux":
        # ZenMux is OpenAI-compatible; route via openai/ prefix with custom base_url
        model_part = model_name.split("/", 1)[1] if "/" in model_name else model_name
        model_name = f"openai/{model_part}"
        extra_kwargs["base_url"] = "https://zenmux.ai/api/v1"
    elif provider == "openrouter":
        os.environ["OPENROUTER_API_KEY"] = api_key
    elif provider == "mistral":
        os.environ["MISTRAL_API_KEY"] = api_key
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
    
    if provider not in ["openai", "openrouter", "zenmux"]:
        llm_params["num_retries"] = 5

    return LLM(**llm_params)


