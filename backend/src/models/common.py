from typing import Tuple

import pandas as pd


def resolve_coordinate_columns(csv_data: pd.DataFrame) -> Tuple[str, str]:
    col_map = {column.lower(): column for column in csv_data.columns}
    long_col = col_map.get("long") or col_map.get("longitude")
    lat_col = col_map.get("lat") or col_map.get("latitude")

    if not long_col or not lat_col:
        raise ValueError("CSV must contain 'Long'/'Longitude' and 'Lat'/'Latitude' columns")

    return long_col, lat_col


def resolve_timestamp_column(csv_data: pd.DataFrame) -> str | None:
    col_map = {column.lower(): column for column in csv_data.columns}
    return col_map.get("timestamp")
