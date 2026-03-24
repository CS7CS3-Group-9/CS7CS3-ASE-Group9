import pandas as pd

# Match the backend bounding box to avoid dropping valid Dublin stops.
MIN_LAT, MAX_LAT = 53.2, 53.5
MIN_LON, MAX_LON = -6.5, -6.0

df = pd.read_csv(
    "GTFS/stops.txt",
    dtype={"stop_id": str},
    low_memory=False,
)

# Ensure numeric lat/lon; drop rows without coordinates.
df["stop_lat"] = pd.to_numeric(df.get("stop_lat"), errors="coerce")
df["stop_lon"] = pd.to_numeric(df.get("stop_lon"), errors="coerce")
df = df.dropna(subset=["stop_lat", "stop_lon"]).copy()

# Filter to Dublin bounding box.
within_bbox = (
    (df["stop_lat"] >= MIN_LAT)
    & (df["stop_lat"] <= MAX_LAT)
    & (df["stop_lon"] >= MIN_LON)
    & (df["stop_lon"] <= MAX_LON)
)

dublin_stops = df.loc[within_bbox].copy()
dublin_stops.to_csv("stops_dublin.txt", index=False)
