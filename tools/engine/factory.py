import os
import logging
from typing import Optional, Dict, Any
from tools.engine.base import IaCEngine
from tools.engine.terraform_engine import TerraformEngine
from tools.engine.opentofu_engine import OpenTofuEngine

logger = logging.getLogger(__name__)

class EngineFactory:
    """Factory to discover, instantiate, and manage IaC execution engines."""

    _ENGINES: Dict[str, IaCEngine] = {
        "terraform": TerraformEngine(),
        "opentofu": OpenTofuEngine(),
        "tofu": OpenTofuEngine(),
    }

    @classmethod
    def get_engine(cls, engine_name: Optional[str] = None) -> IaCEngine:
        """
        Get the requested IaC engine instance.
        If engine_name is None, uses DEFAULT_IAC_ENGINE from env or defaults to 'terraform'.
        If the requested engine binary is not installed, it falls back to an available engine.
        """
        requested = (engine_name or os.getenv("DEFAULT_IAC_ENGINE", "terraform")).lower().strip()
        
        # Normalize aliases
        if requested in ("tofu", "opentofu"):
            engine_key = "opentofu"
        else:
            engine_key = "terraform"

        engine = cls._ENGINES.get(engine_key, cls._ENGINES["terraform"])

        # Check binary availability
        if not engine.is_available():
            # Attempt fallback
            fallback_key = "terraform" if engine_key == "opentofu" else "opentofu"
            fallback_engine = cls._ENGINES[fallback_key]
            
            if fallback_engine.is_available():
                logger.warning(
                    f"Requested engine '{engine.name}' (binary '{engine.binary}') not found on PATH. "
                    f"Falling back to '{fallback_engine.name}' (binary '{fallback_engine.binary}')."
                )
                return fallback_engine
            else:
                logger.warning(
                    f"Neither '{engine.binary}' nor '{fallback_engine.binary}' found on PATH. "
                    f"Proceeding with '{engine.name}' (CLI calls will report missing binary)."
                )

        return engine

    @classmethod
    def list_available_engines(cls) -> Dict[str, Any]:
        """Return availability status and versions for all supported engines."""
        tf = cls._ENGINES["terraform"]
        tofu = cls._ENGINES["opentofu"]
        return {
            "terraform": {
                "installed": tf.is_available(),
                "version": tf.get_version(),
                "binary": tf.binary
            },
            "opentofu": {
                "installed": tofu.is_available(),
                "version": tofu.get_version(),
                "binary": tofu.binary
            },
            "default": os.getenv("DEFAULT_IAC_ENGINE", "terraform")
        }
