from tools.engine.base import IaCEngine

class TerraformEngine(IaCEngine):
    """Concrete IaC engine implementation for HashiCorp Terraform."""

    @property
    def name(self) -> str:
        return "terraform"

    @property
    def binary(self) -> str:
        return "terraform"
