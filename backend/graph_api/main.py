from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(title="Graph API Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

from graph_api.routes import router as graph_router
app.include_router(graph_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "graph_api"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("graph_api.main:app", host=settings.api_host, port=settings.graph_api_port, reload=True)
