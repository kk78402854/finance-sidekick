import uvicorn

from assistant.api.dependencies import init_dialogue_engine
from assistant.conf.config import settings


def mian():
    # 数据库引擎、建表、http 客户端都在 app lifespan 里初始化，
    # 避免事件循环不同导致连接池绑定到已关闭的 loop
    init_dialogue_engine()
    uvicorn.run('assistant.api.app:app',
                host=settings.app_host,
                port=settings.app_port,
                )


if __name__ == '__main__':
    mian()
