from abc import ABC, abstractmethod
from typing import Any, Dict, Type, TypeVar


S = TypeVar("S", bound="Serializable")


class Serializable(ABC):
    @classmethod
    @abstractmethod
    def deserialize(cls: Type[S], serialized: Dict[str, Any]) -> S:
        raise NotImplementedError()

    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        raise NotImplementedError()
