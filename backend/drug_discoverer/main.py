from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(title="Drug Discoverer Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

from drug_discoverer.routes import router as discovery_router
app.include_router(discovery_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "drug_discoverer"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("drug_discoverer.main:app", host=settings.api_host, port=settings.drug_discoverer_port, reload=True)
