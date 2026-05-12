import os
import litellm
import google.generativeai as genai
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

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

        prompt = litellm_messages[-1]["content"] if litellm_messages else ""

        # 1. Primary Attempt for Gemini: Official SDK
        if "gemini" in self.model_name.lower():
            print(f"[Wrapper] Using Official Google SDK for {self.model_name}...")
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
                print(f"[Wrapper] Official SDK failed: {str(sdk_err)}. Trying LiteLLM fallback...")

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
