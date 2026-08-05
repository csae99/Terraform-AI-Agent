import os
import litellm
import google.generativeai as genai
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

_last_gemini_call_time = 0.0  # Module-level tracker for Gemini free-tier throttling

class FallbackChatModel(BaseChatModel):
    """
    A custom LangChain Chat Model that uses LiteLLM with a hard fallback 
    to the official Google Generative AI SDK for Gemini models.
    """
    model_name: str
    temperature: float = 0.7

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        print(f"\n[Wrapper] _generate invoked for model: {self.model_name}")
        # Convert LangChain messages to LiteLLM format
        litellm_messages = []
        for m in messages:
            role = "user"
            if m.type == "ai": role = "assistant"
            elif m.type == "system": role = "system"
            litellm_messages.append({"role": role, "content": m.content})

        is_gemini = "gemini" in self.model_name.lower() or "google_ai" in self.model_name.lower() or "google/" in self.model_name.lower()
        if is_gemini and os.getenv("GEMINI_FREE_TIER_THROTTLE", "true").lower() == "true":
            import time
            global _last_gemini_call_time
            
            now = time.time()
            elapsed = now - _last_gemini_call_time
            if elapsed < 4.2:
                sleep_time = 4.2 - elapsed
                print(f"[Rate Limiter] Throttling Gemini API call by {sleep_time:.2f}s to respect 15 RPM free tier limit...")
                time.sleep(sleep_time)
            _last_gemini_call_time = time.time()

        prompt = litellm_messages[-1]["content"] if litellm_messages else ""

        # 1. Primary Attempt for Gemini: Official SDK
        if "gemini" in self.model_name.lower():
            print(f"[Wrapper] Using Official Google SDK for {self.model_name}...")
            import time
            import re
            max_retries = 3
            retry_delay = 5.0
            for attempt in range(max_retries):
                try:
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
                    clean_model = self.model_name.split("/")[-1] if "/" in self.model_name else self.model_name
                    # Ensure we use a supported model string
                    if "flash" in clean_model: clean_model = "gemini-1.5-flash"
                    elif "pro" in clean_model: clean_model = "gemini-1.5-pro"
                    
                    sdk_model = genai.GenerativeModel(clean_model)
                    response = sdk_model.generate_content(prompt)
                    content = response.text
                    ai_message = AIMessage(content=content)
                    return ChatResult(generations=[ChatGeneration(message=ai_message)])
                    
                except Exception as sdk_err:
                    err_str = str(sdk_err).lower()
                    is_rate_limit = any(kw in err_str for kw in ["429", "exhausted", "quota", "rate", "limit"])
                    if is_rate_limit and attempt < max_retries - 1:
                        match_secs = re.search(r"retry\s+in\s+([\d\.]+)\s*s", err_str, re.IGNORECASE)
                        match_delay = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", err_str, re.IGNORECASE)
                        if match_secs:
                            retry_delay = float(match_secs.group(1)) + 1.0
                        elif match_delay:
                            retry_delay = float(match_delay.group(1)) + 1.0
                        else:
                            retry_delay = 5.0 * (2 ** attempt)
                        
                        print(f"[Wrapper] Official SDK hit rate limit. Waiting {retry_delay:.2f}s before retry (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(retry_delay)
                    else:
                        print(f"[Wrapper] Official SDK failed: {str(sdk_err)}. Trying LiteLLM fallback...")
                        break

        # 2. Secondary Attempt: LiteLLM (Fallback or Non-Gemini)
        try:
            response = litellm.completion(
                model=self.model_name,
                messages=litellm_messages,
                temperature=self.temperature,
                **kwargs
            )
            content = response.choices[0].message.content
            ai_message = AIMessage(content=content)
            return ChatResult(generations=[ChatGeneration(message=ai_message)])
            
        except Exception as e:
            print(f"[Wrapper] LiteLLM completion also failed: {str(e)}")
            raise e

        ai_message = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    @property
    def _llm_type(self) -> str:
        return "fallback-chat-model"
