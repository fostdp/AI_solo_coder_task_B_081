from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os

from shared.config import get_settings

app = FastAPI(title="TCM Gateway", version="2.0.0",
              description="中医药方剂系统网关 - 路由分发至4个微服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

settings = get_settings()

SERVICE_MAP = {
    "/formulas": f"http://localhost:{settings.formula_loader_port}",
    "/herbs": f"http://localhost:{settings.formula_loader_port}",
    "/diseases": f"http://localhost:{settings.formula_loader_port}",
    "/import": f"http://localhost:{settings.formula_loader_port}",
    "/mining": f"http://localhost:{settings.pattern_miner_port}",
    "/discovery": f"http://localhost:{settings.drug_discoverer_port}",
    "/graph": f"http://localhost:{settings.graph_api_port}",
}

client = httpx.AsyncClient(timeout=30.0)


def _resolve_service(path: str):
    for prefix, url in SERVICE_MAP.items():
        if path.startswith(prefix):
            return url + path
    return None


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    target_url = _resolve_service("/" + path)
    if target_url is None:
        return JSONResponse(status_code=404, content={"detail": f"无匹配服务: /{path}"})

    try:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)

        resp = await client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers=headers,
            params=dict(request.query_params),
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse(status_code=502, content={"detail": f"服务不可达: {target_url}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.get("/")
def root():
    return {
        "name": "中医药方剂配伍规律挖掘系统 (微服务版)",
        "version": "2.0.0",
        "services": {
            "formula_loader": f"http://localhost:{settings.formula_loader_port}",
            "pattern_miner": f"http://localhost:{settings.pattern_miner_port}",
            "drug_discoverer": f"http://localhost:{settings.drug_discoverer_port}",
            "graph_api": f"http://localhost:{settings.graph_api_port}",
        },
        "gateway": f"http://localhost:{settings.gateway_port}"
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "gateway"}


@app.get("/api/stats")
def get_stats():
    from shared.database import get_collection
    formulas_col = get_collection("formulas")
    herbs_col = get_collection("herbs")
    diseases_col = get_collection("diseases")
    return {
        "formulas_count": formulas_col.count_documents({}),
        "herbs_count": herbs_col.count_documents({}),
        "diseases_count": diseases_col.count_documents({})
    }


frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(frontend_dir):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gateway:app", host=settings.api_host, port=settings.gateway_port, reload=True)
