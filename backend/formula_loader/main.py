from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config import get_settings

app = FastAPI(title="Formula Loader Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from formula_loader.routes_formulas import router as formulas_router
from formula_loader.routes_herbs import router as herbs_router
from formula_loader.routes_diseases import router as diseases_router
from formula_loader.routes_import import router as import_router
from api.efficacy import router as efficacy_router

app.include_router(formulas_router)
app.include_router(herbs_router)
app.include_router(diseases_router)
app.include_router(import_router)
app.include_router(efficacy_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "formula_loader"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("formula_loader.main:app", host=settings.api_host, port=settings.formula_loader_port, reload=True)
