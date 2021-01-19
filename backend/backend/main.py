import logging
import sys

from fastapi import BackgroundTasks, FastAPI, File, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.logs import InterceptHandler, format_record, logger
from backend.parser import SSProcessor

# LOGGING
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "level": logging.DEBUG,
            "format": format_record,
            "backtrace": True,
        },
    ],
)
logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]

app = FastAPI(
    title="Stormspotter-Backend",
    description="API Handler for Stormspotter",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sshandler = SSProcessor()


@app.post("/api/upload")
async def process_upload(
    task: BackgroundTasks,
    x_neo4j_user: str = Header("neo4j"),
    x_neo4j_pass: str = Header("password"),
    upload: UploadFile = File(...),
):
    upload.file.rollover()
    task.add_task(
        sshandler.process,
        upload.file._file,
        upload.filename,
        x_neo4j_user,
        x_neo4j_pass,
    )
    return {"status": "Upload Success"}
