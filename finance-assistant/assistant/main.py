import uvicorn

from assistant.api.dependencies import init_dialogue_engine
from assistant.conf.config import settings
from assistant.utils.db import init_db_engine
from assistant.utils.httpx_client import init_http_client


def mian():
    init_db_engine()
    init_dialogue_engine()
    init_http_client()
    uvicorn.run('assistant.api.app:app',
                host=settings.app_host,
                port=settings.app_port,
                )
    # reload=True,


if __name__ == '__main__':
    mian()
