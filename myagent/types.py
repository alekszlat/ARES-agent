import abc

class BaseModel:
    @abc.abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        ...