import logging

# Reduce Azure HTTP logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
