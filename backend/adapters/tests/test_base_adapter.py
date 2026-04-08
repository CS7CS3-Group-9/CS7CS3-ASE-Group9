import pytest
from backend.adapters.base_adapter import DataAdapter


class TestDataAdapter:
    def test_fetch_not_implemented(self):
        adapter = DataAdapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch("test_location")

    def test_source_name_not_implemented(self):
        adapter = DataAdapter()
        with pytest.raises(NotImplementedError):
            adapter.source_name()
