"""Container entrypoint: one process, signal-safe Uvicorn startup."""
import os
import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=1,
                reload=False, access_log=False, timeout_graceful_shutdown=30)


if __name__ == "__main__":
    main()
