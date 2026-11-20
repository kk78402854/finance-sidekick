"""
创建fastapi对象
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from assistant.api.chat_router import chat_router
from assistant.api.portal_router import portal_router
from assistant.utils.db import close_db_engine, create_tables, init_db_engine
from assistant.utils.finance_readonly_db import close_finance_db
from assistant.utils.httpx_client import close_http_client, init_http_client

# 静态页面目录（web 下按角色拆成多个页面）
WEB_DIR = Path(__file__).parents[2] / "web"

# 页面路由 -> 静态文件，保持 URL 语义清晰
PAGES: dict[str, str] = {
    "/": "index.html",
    "/chat": "chat.html",
    "/customer/profile": "customer/profile.html",
    "/customer/accounts": "customer/accounts.html",
    "/customer/transactions": "customer/transactions.html",
    "/customer/credit-loans": "customer/credit-loans.html",
    "/customer/tickets": "customer/tickets.html",
    "/admin/dashboard": "admin/dashboard.html",
    "/admin/customers": "admin/customers.html",
    "/admin/customer-detail": "admin/customer-detail.html",
    "/admin/loan-approvals": "admin/loan-approvals.html",
    "/admin/tickets": "admin/tickets.html",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 数据库使用对象初始化操作
    init_db_engine()
    # 首次启动自动建表：dialogue_states、faq_items
    await create_tables()
    # 远程调用对象初始化操作
    init_http_client()
    yield
    await close_db_engine()
    await close_finance_db()
    await close_http_client()


app = FastAPI(lifespan=lifespan)
app.include_router(chat_router)
app.include_router(portal_router)

if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    def _page_handler(filename: str):
        async def _serve() -> FileResponse:
            return FileResponse(WEB_DIR / filename)

        return _serve

    for page_path, filename in PAGES.items():
        app.add_api_route(
            page_path,
            _page_handler(filename),
            methods=["GET"],
            include_in_schema=False,
        )
