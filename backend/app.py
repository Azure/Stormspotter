import uvicorn


def main():
    uvicorn.run(
        "backend.main:app", reload=False, host="127.0.0.1", port=9090,
    )


if __name__ == "__main__":
    main()
