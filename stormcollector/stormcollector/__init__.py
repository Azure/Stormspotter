from datetime import datetime
from pathlib import Path

__version__ = "1.0.0"
OUTPUT_FOLDER = Path(f"results_{datetime.now().strftime('%Y%m%d-%H%M%S')}")
