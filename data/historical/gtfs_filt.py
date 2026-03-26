import pandas as pd

# Read filtered Dublin stops
stops = pd.read_csv(
    "stops_dublin.txt",
    encoding="utf-8-sig",
    dtype={"stop_id": str},
    low_memory=False,
)
stops.columns = stops.columns.str.strip()
stops["stop_id"] = stops["stop_id"].str.strip()

# Read stop_times
stop_times = pd.read_csv(
    "GTFS/stop_times.txt",
    encoding="utf-8-sig",
    dtype={"stop_id": str},
    low_memory=False,
)
stop_times.columns = stop_times.columns.str.strip()
stop_times["stop_id"] = stop_times["stop_id"].str.strip()

# Keep only stop_times rows whose stop_id is in the Dublin stops file
dublin_stop_ids = set(stops["stop_id"])
filtered_stop_times = stop_times[stop_times["stop_id"].isin(dublin_stop_ids)].copy()

# Save
filtered_stop_times.to_csv("stop_times_dublin.txt", index=False)

print(f"Original stop_times rows: {len(stop_times)}")
print(f"Filtered stop_times rows: {len(filtered_stop_times)}")
