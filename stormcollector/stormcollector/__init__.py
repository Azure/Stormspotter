from datetime import datetime
from pathlib import Path

OUTPUT_FOLDER = Path(f"results_{datetime.now().strftime('%Y%m%d-%H%M%S')}")
SSL_CONTEXT = None
