from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv


# ---- Encryption round-trip test ----
def test_aes_encryption_round_trip():
    key = Fernet.generate_key()
    f = Fernet(key)

    msg = b"super secret"
    encrypted = f.encrypt(msg)
    decrypted = f.decrypt(encrypted)

    assert decrypted == msg


# ---- Environment secrets loading (multiple secrets) ----
def test_env_secret_loading_multiple(tmp_path, monkeypatch):
    # Create a temporary .env file with multiple secrets
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_KEY=123456\n" "DB_PASSWORD=pass123\n" "SECRET_TOKEN=tok987"
    )

    # Load the .env file using python-dotenv
    load_dotenv(str(env_file))

    # Verify that all secrets are loaded correctly
    assert os.getenv("API_KEY") == "123456"
    assert os.getenv("DB_PASSWORD") == "pass123"
    assert os.getenv("SECRET_TOKEN") == "tok987"
