class DataAdapter:
    def fetch(self, location: str):
        raise NotImplementedError

    def source_name(self) -> str:
        raise NotImplementedError
