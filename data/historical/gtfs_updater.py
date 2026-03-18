import io
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests

# -----------------------------
# CONFIGURATION
# -----------------------------

GTFS_URL = "https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip"

DEFAULT_GTFS_DIR = r"C:\Users\omallech\Documents\CS7CS3-ASE-Group9\data\historical\GTFS"

COOLDOWN_SECONDS = 3600  # 1 hour

STATE_FILENAME = "_last_updated_epoch.txt"


def get_headers():
    return {}


# -----------------------------
# FILTER DUBLIN STOP TIMES
# -----------------------------
def filter_dublin_stop_times(target_dir: Path):
    stops_file = target_dir / "stops.txt"
    stop_times_file = target_dir / "stop_times.txt"

    if not stops_file.exists() or not stop_times_file.exists():
        print("[GTFS Updater] Missing stops.txt or stop_times.txt — skipping filter.")
        return

    print("[GTFS Updater] Filtering Dublin stop_times...")

    # Dublin bounding box (approx)
    DUBLIN_LAT_MIN = 53.2
    DUBLIN_LAT_MAX = 53.5
    DUBLIN_LON_MIN = -6.5
    DUBLIN_LON_MAX = -6.0

    dublin_stop_ids = set()

    # Read stops.txt
    with open(stops_file, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        col_index = {name: i for i, name in enumerate(header)}

        for line in f:
            parts = line.strip().split(",")

            try:
                lat = float(parts[col_index["stop_lat"]])
                lon = float(parts[col_index["stop_lon"]])
                stop_id = parts[col_index["stop_id"]]
            except (ValueError, KeyError, IndexError):
                continue

            if (
                DUBLIN_LAT_MIN <= lat <= DUBLIN_LAT_MAX
                and DUBLIN_LON_MIN <= lon <= DUBLIN_LON_MAX
            ):
                dublin_stop_ids.add(stop_id)

    print(f"[GTFS Updater] Found {len(dublin_stop_ids)} Dublin stops.")

    # Filter stop_times.txt
    temp_output = target_dir / "stop_times_filtered.txt"

    kept = 0
    total = 0

    with open(stop_times_file, "r", encoding="utf-8") as infile, \
         open(temp_output, "w", encoding="utf-8") as outfile:

        header = infile.readline()
        outfile.write(header)

        cols = header.strip().split(",")
        stop_id_index = cols.index("stop_id")

        for line in infile:
            total += 1
            parts = line.strip().split(",")

            if parts[stop_id_index] in dublin_stop_ids:
                outfile.write(line)
                kept += 1

    os.replace(temp_output, stop_times_file)

    print(f"[GTFS Updater] Filtered stop_times: kept {kept}/{total} rows.")


# -----------------------------
# GENERATE STOP VISIT COUNTS
# -----------------------------
def generate_stop_visit_counts(target_dir: Path):
    stop_times_file = target_dir / "stop_times.txt"
    output_file = target_dir / "stop_visit_counts.txt"

    if not stop_times_file.exists():
        print("[GTFS Updater] stop_times.txt not found — skipping counts.")
        return

    print("[GTFS Updater] Generating stop visit counts...")

    counts = {}

    with open(stop_times_file, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        stop_id_index = header.index("stop_id")

        for line in f:
            parts = line.strip().split(",")

            try:
                stop_id = parts[stop_id_index]
            except IndexError:
                continue

            counts[stop_id] = counts.get(stop_id, 0) + 1

    # Write results
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("stop_id,visit_count\n")
        for stop_id, count in counts.items():
            f.write(f"{stop_id},{count}\n")

    print(f"[GTFS Updater] Wrote {len(counts)} stop counts.")


# -----------------------------
# DOWNLOAD + EXTRACT
# -----------------------------
def download_and_extract(target_dir: Path):
    print(f"[GTFS Updater] Target Directory: {target_dir}")
    print(f"[GTFS Updater] Downloading from {GTFS_URL}")

    try:
        r = requests.get(GTFS_URL, headers=get_headers(), timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"[GTFS Updater] Error downloading: {e}")
        return False

    temp_zip = target_dir / "temp_update.zip"

    try:
        with open(temp_zip, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        print(f"[GTFS Updater] Error saving zip: {e}")
        return False

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

    print("[GTFS Updater] Updating files...")
    updated_count = 0

    for item in temp_extract.iterdir():
        dest = target_dir / item.name

        if dest.exists():
            if dest.is_file():
                dest.unlink()
            else:
                shutil.rmtree(dest)

        shutil.move(str(item), str(dest))
        updated_count += 1

    print(f"[GTFS Updater] Updated {updated_count} files.")

    # Step 1: filter Dublin data
    filter_dublin_stop_times(target_dir)

    # Step 2: generate counts
    generate_stop_visit_counts(target_dir)

    # Cleanup
    shutil.rmtree(temp_extract)
    temp_zip.unlink()

    # Update state
    state_file = target_dir / STATE_FILENAME
    with open(state_file, "w") as f:
        f.write(str(int(time.time())))

    now = datetime.now().isoformat()
    with open(target_dir / "last_updated_log.txt", "w") as f:
        f.write(f"Last successful update: {now}\n")

    print("[GTFS Updater] Update complete.")
    return True


# -----------------------------
# COOLDOWN CHECK
# -----------------------------
def can_update(target_dir: Path) -> bool:
    state_file = target_dir / STATE_FILENAME

    if not state_file.exists():
        return True

    try:
        last_epoch = int(state_file.read_text().strip())
    except (ValueError, OSError):
        return True

    current_epoch = int(time.time())

    if (current_epoch - last_epoch) >= COOLDOWN_SECONDS:
        print("[GTFS Updater] Cooldown passed. Checking for updates...")
        return True
    else:
        print("[GTFS Updater] Cooldown active. Skipping download.")
        return False


# -----------------------------
# MAIN
# -----------------------------
def main():
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        target_path = DEFAULT_GTFS_DIR

    target_dir = Path(target_path).resolve()

    if not target_dir.exists():
        print(f"Error: Target directory does not exist: {target_dir}")
        sys.exit(1)

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
