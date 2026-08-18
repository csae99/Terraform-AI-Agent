import os
from tools.engine.base import IaCEngine

class OpenTofuEngine(IaCEngine):
    """Concrete IaC engine implementation for OpenTofu (open-source fork)."""

    @property
    def name(self) -> str:
        return "opentofu"

    @property
    def binary(self) -> str:
        return "tofu"
