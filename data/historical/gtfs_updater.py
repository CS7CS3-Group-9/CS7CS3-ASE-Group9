import io
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

# -----------------------------
# CONFIGURATION
# -----------------------------

# The official source for the data you are using (Waterford/Dublin/etc)
# If this URL changes, you just update it here.
GTFS_URL = "https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip"

# Default path matches your folder structure
# You can override this by passing the path as an argument when running the script.
DEFAULT_GTFS_DIR = r"C:\Users\Ruby\Documents\GitHub\CS7CS3-ASE-Group9\data\historical\GTFS"

# How long to wait before checking again (seconds).
# This prevents downloading every time you run the script if nothing changed.
COOLDOWN_SECONDS = 3600  # 1 hour

STATE_FILENAME = "_last_updated_epoch.txt"


def get_headers():
    # If you have an API key for NTA, add it here.
    # The public zip usually doesn't need one, but if you use the specific API endpoint:
    # return {"x-api-key": "YOUR_KEY"}
    return {}


def download_and_extract(target_dir: Path):
    print(f"[GTFS Updater] Target Directory: {target_dir}")
    print(f"[GTFS Updater] Downloading from {GTFS_URL}")

    try:
        r = requests.get(GTFS_URL, headers=get_headers(), timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"[GTFS Updater] Error downloading: {e}")
        return False

    # 1. Save to a temp zip file
    temp_zip = target_dir / "temp_update.zip"
    try:
        with open(temp_zip, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        print(f"[GTFS Updater] Error saving zip: {e}")
        return False

    # 2. Extract to a temp folder to avoid corrupting data if extraction fails halfway
    temp_extract = target_dir / "temp_extract"
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)

    print("[GTFS Updater] Extracting...")
    try:
        with zipfile.ZipFile(temp_zip, "r") as z:
            z.extractall(temp_extract)
    except Exception as e:
        print(f"[GTFS Updater] Error extracting zip: {e}")
        return False

    # 3. Move files to target dir (Overwriting existing ones)
    # We specifically look for .txt files to overwrite
    print("[GTFS Updater] Updating files...")
    updated_count = 0

    for item in temp_extract.iterdir():
        dest = target_dir / item.name

        # If destination exists, delete it (file or folder)
        if dest.exists():
            if dest.is_file():
                dest.unlink()
            else:
                shutil.rmtree(dest)

        # Move new file
        shutil.move(str(item), str(dest))
        updated_count += 1

    print(f"[GTFS Updater] Updated {updated_count} files.")

    # 4. Cleanup
    shutil.rmtree(temp_extract)
    temp_zip.unlink()

    # 5. Update State File
    state_file = target_dir / STATE_FILENAME
    with open(state_file, "w") as f:
        f.write(str(int(time.time())))

    now = datetime.now().isoformat()
    with open(target_dir / "last_updated_log.txt", "w") as f:
        f.write(f"Last successful update: {now}\n")

    print(f"[GTFS Updater] Update complete.")
    return True


def can_update(target_dir: Path) -> bool:
    """
    Checks if the cooldown period has passed.
    """
    state_file = target_dir / STATE_FILENAME
    if not state_file.exists():
        return True  # No history, so update allowed

    try:
        last_epoch = int(state_file.read_text().strip())
    except (ValueError, OSError):
        return True  # Corrupt state, allow update

    current_epoch = int(time.time())

    if (current_epoch - last_epoch) >= COOLDOWN_SECONDS:
        print("[GTFS Updater] Cooldown passed. Checking for updates...")
        return True
    else:
        print("[GTFS Updater] Cooldown active. Skipping download.")
        return False


def main():
    # 1. Determine Target Directory
    # Use argument if provided, else use default
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        target_path = DEFAULT_GTFS_DIR

    target_dir = Path(target_path).resolve()

    if not target_dir.exists():
        print(f"Error: Target directory does not exist: {target_dir}")
        sys.exit(1)

    # 2. Check if we should update
    if can_update(target_dir):
        success = download_and_extract(target_dir)
        if success:
            print("Success!")
        else:
            print("Failed.")
    else:
        print("No update performed (within cooldown period).")


if __name__ == "__main__":
    main()
