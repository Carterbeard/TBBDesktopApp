"""
Application constants
"""

# Required CSV columns
REQUIRED_COLUMNS = ["Sample_id", "timestamp", "Long", "Lat"]

# Coordinate validation ranges
COORDINATE_RANGES = {
    "Long": (-180.0, 180.0),
    "Lat": (-90.0, 90.0),
}

# Processing statuses
class ProcessingStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Conservative tracer keywords
CONSERVATIVE_TRACER_KEYWORDS = {
    # Major ions - include BOTH original and normalized versions
    "chloride", "cl", "cl-", "cl",  # "cl-" and "cl" both included
    "bromide", "br", "br-", "br",
    "sodium", "na", "na+", "na",
    "potassium", "k", "k+", "k",
    "magnesium", "mg", "mg2+", "mg2", "mg",
    "calcium", "ca", "ca2+", "ca2", "ca",
    # Isotopes
    "δ18o", "d18o", "δ2h", "d2h",
    # Other
    "conductivity", "ec",
}