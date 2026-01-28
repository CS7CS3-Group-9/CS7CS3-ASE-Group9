from abc import ABC, abstractmethod
from backend.models.mobility_snapshot import MobilitySnapshot


class DataAdapter(ABC):
    @abstractmethod
    def fetch(self, location: str):
        raise NotImplementedError

    def source_name(self) -> str:
        raise NotImplementedError
