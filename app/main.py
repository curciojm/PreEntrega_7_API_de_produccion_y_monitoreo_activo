from fastapi import FastAPI
import uvicorn

app = FastAPI(title="PreEntrega 7 - Multi-Agent API")

# ... tus endpoints ...


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )