from llm.config import get_llm

class BaseAgent:
    def __init__(self, model_name=None, api_key=None):
        self.llm = get_llm(model_name, api_key)
