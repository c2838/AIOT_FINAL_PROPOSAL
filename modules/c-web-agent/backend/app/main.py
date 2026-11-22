from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.api.routes import routes
from app.providers.interfaces import Problem
from app.services.runtime import Runtime


def create_app(settings=None):
    rt = Runtime(settings)
    app = FastAPI(title="居家環境與外出建議代理人", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET","POST","PUT"], allow_headers=["Content-Type"], expose_headers=["X-Data-Mode"])

    @app.middleware("http")
    async def source_header(request, call_next):
        response = await call_next(request)
        response.headers["X-Data-Mode"] = rt.cfg.data_mode
        return response

    def error(status, code, msg):
        return JSONResponse({"error":{"code":code,"message":msg}}, status_code=status)

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return error(exc.http, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        fields = ", ".join(".".join(map(str,e["loc"])) for e in exc.errors())
        return error(422, "invalid", "請檢查欄位：" + fields)

    @app.exception_handler(HTTPException)
    async def http_handler(request, exc):
        return error(exc.status_code, "missing" if exc.status_code == 404 else "http_error", "路徑或請求方式無效。")

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        return error(500, "internal_error", "服務暫時無法完成請求。")

    app.include_router(routes(rt))
    return app


app = create_app()
