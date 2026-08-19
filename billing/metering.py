import re
from typing import Dict, Any, Optional

class UsageMeter:
    """
    Multi-Dimensional Usage Meter:
    1. AI Token Metering & Cost estimation across LLM providers.
    2. Platform Compute Metering (Worker seconds * compute cost).
    3. Infrastructure Cost Attribution (Infracost cloud estimate).
    """

    # Model Pricing per 1,000 tokens (USD)
    # [Prompt Cost per 1k, Completion Cost per 1k]
    MODEL_PRICING = {
        "gemini/gemini-2.0-flash": (0.00010, 0.00040),
        "gemini/gemini-1.5-pro": (0.00125, 0.00500),
        "gemini/gemini-1.5-flash": (0.000075, 0.00030),
        "openai/gpt-4o": (0.00250, 0.01000),
        "openai/gpt-4o-mini": (0.00015, 0.00060),
        "anthropic/claude-3-5-sonnet": (0.00300, 0.01500),
        "anthropic/claude-3-haiku": (0.00025, 0.00125),
        "groq/llama-3.3-70b": (0.00059, 0.00079),
        "mistral/mistral-large": (0.00200, 0.00600),
        "zenmux": (0.00020, 0.00080),
        "default": (0.00050, 0.00150)
    }

    # Worker Compute Cost per second (e.g. $0.05 / hour = ~$0.000014 / sec)
    COMPUTE_RATE_PER_SECOND = 0.000020

    @classmethod
    def estimate_tokens(cls, prompt_text: str, generated_code_len: int = 0, healing_rounds: int = 0) -> Dict[str, int]:
        """
        Estimates prompt and completion tokens when raw usage headers are not available.
        Standard approximation: ~4 characters per token + agent orchestration overhead.
        """
        base_prompt_tokens = max(100, int(len(prompt_text or "") / 3.5))
        # 7 agents with system prompts, schema specs, tools definitions ~ 2,500 prompt tokens per round
        orchestration_prompt_tokens = 2500 * (1 + healing_rounds)
        total_prompt_tokens = base_prompt_tokens + orchestration_prompt_tokens

        # Completion tokens from code generation + reports
        base_completion_tokens = max(300, int(generated_code_len / 3.5)) if generated_code_len > 0 else 1200
        healing_completion_tokens = 800 * healing_rounds
        total_completion_tokens = base_completion_tokens + healing_completion_tokens

        return {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens
        }

    @classmethod
    def calculate_ai_cost(cls, model_name: Optional[str], prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates estimated AI model cost in USD."""
        model_key = (model_name or "").lower()
        pricing = cls.MODEL_PRICING.get("default")
        
        for k, v in cls.MODEL_PRICING.items():
            if k in model_key:
                pricing = v
                break

        prompt_cost = (prompt_tokens / 1000.0) * pricing[0]
        completion_cost = (completion_tokens / 1000.0) * pricing[1]
        return round(prompt_cost + completion_cost, 6)

    @classmethod
    def calculate_compute_cost(cls, duration_seconds: float) -> float:
        """Calculates platform worker execution compute cost in USD."""
        return round(max(0.0, duration_seconds) * cls.COMPUTE_RATE_PER_SECOND, 6)

    @classmethod
    def compute_cost_attribution(cls, prompt_tokens: int, completion_tokens: int, model_name: Optional[str],
                                 duration_seconds: float, infra_monthly_cost: float = 0.0) -> Dict[str, Any]:
        """
        Computes the complete 3-way cost attribution for a single execution:
        AI Token Cost + Platform Compute Cost + Cloud Infrastructure Projected Cost.
        """
        ai_cost = cls.calculate_ai_cost(model_name, prompt_tokens, completion_tokens)
        compute_cost = cls.calculate_compute_cost(duration_seconds)
        total_platform_cost = round(ai_cost + compute_cost, 4)

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "ai_cost_usd": ai_cost,
            "compute_seconds": round(duration_seconds, 2),
            "compute_cost_usd": compute_cost,
            "infra_monthly_projected_usd": round(infra_monthly_cost, 2),
            "total_platform_cost_usd": total_platform_cost,
            "total_run_cost_usd": round(total_platform_cost + infra_monthly_cost, 2)
        }
