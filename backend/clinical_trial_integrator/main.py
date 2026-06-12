from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(title="Clinical Trial Integrator Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from clinical_trial_integrator.routes import router as clinical_router
app.include_router(clinical_router)


@app.get("/")
async def root():
    return {
        "service": "clinical_trial_integrator",
        "version": "2.0.0",
        "status": "running",
        "endpoints": [
            "/efficacy/clinical/trials",
            "/efficacy/clinical/meta-analysis",
            "/efficacy/clinical/network-meta",
            "/efficacy/clinical/formula-evidence-batch",
            "/efficacy/summary/indication/{indication}",
        ],
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "clinical_trial_integrator"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("clinical_trial_integrator.main:app", host=settings.api_host, port=settings.clinical_trial_integrator_port, reload=True)
