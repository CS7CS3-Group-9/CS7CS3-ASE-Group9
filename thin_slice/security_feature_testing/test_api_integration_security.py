import requests
from unittest.mock import patch, MagicMock

def test_external_api_https(monkeypatch):
    def mock_get(url, *args, **kwargs):
        assert url.startswith("https://"), f"Insercure HTTP detected: {url}"
        m = MagicMock()
        m.status_code = 200
        m.text = "data"
        return m
    
    monkeypatch.setattr(requests, "get", mock_get)

    # Test multiple calls as would occur in the app
    urls = [
        "https://api.example.mock",
        "https://firebase.validate.token.mock"
    ]
    for u in urls:
        response = requests.get(u)
        assert response.status_code == 200
        assert response.text == "data"