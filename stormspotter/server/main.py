import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path


log = logging.getLogger("rich")

app = FastAPI(
    title="Stormspotter Server",
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

app.mount(
    "/css",
    StaticFiles(directory=Path(__file__).parent / "dist/css"),
    name="css",
)
app.mount(
    "/img",
    StaticFiles(directory=Path(__file__).parent / "dist/img"),
    name="img",
)
app.mount(
    "/js",
    StaticFiles(directory=Path(__file__).parent / "dist/js"),
    name="js",
)
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "dist/", html=True),
    name="dist",
)
