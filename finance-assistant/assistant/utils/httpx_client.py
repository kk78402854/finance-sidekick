"""
这个模块目的：发送远程调用，调用中台里面功能接口
"""
import asyncio
import uuid

from httpx import AsyncClient

from assistant.conf.config import settings

## 第一种 使用python内置模块requests
# import requests
# requests.get()

# 异步操作方便
## 第二种 httpx实现
http_client: AsyncClient | None = None

# 创建http_client方法
def init_http_client():
    global http_client
    http_client = AsyncClient(timeout=10.0)

# 关闭http_client方法
async def close_http_client():
    await http_client.aclose()


def finance_headers(customer_no: str, *, with_operator: bool = False) -> dict[str, str]:
    """构造金融中台统一鉴权头。

    - Authorization: Bearer <customer_no>，登录客户身份
    - X-Channel-Code: 渠道编码，缺失或无效会返回 403 CHANNEL_NOT_AVAILABLE
    - X-Request-Id: 请求追踪号
    - X-Operator-No: 员工编号，仅工单类接口需要
    """
    headers = {
        "Authorization": f"Bearer {customer_no}",
        "X-Channel-Code": settings.finance_channel_code,
        "X-Request-Id": str(uuid.uuid4()),
    }
    if with_operator:
        headers["X-Operator-No"] = settings.finance_operator_no
    return headers


# 测试方法
async def test():
    init_http_client()
    result = await http_client.get(
        "http://127.0.0.1:8000/api/v1/customers/CUS00000001/accounts",
        headers=finance_headers("CUS00000001"))
    print(result.json())
    await close_http_client()

if __name__ == "__main__":
    asyncio.run(test())
