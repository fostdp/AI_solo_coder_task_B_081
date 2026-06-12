from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(title="Dose Response Modeler Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from dose_response_modeler.routes import router as dose_response_router
app.include_router(dose_response_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "dose_response_modeler"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("dose_response_modeler.main:app", host=settings.api_host, port=settings.dose_response_modeler_port, reload=True)
