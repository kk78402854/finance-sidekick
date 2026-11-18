# 金融中台 finance-data API 镜像
# 基础镜像可通过 --build-arg BASE_IMAGE 换成镜像站，例如
#   docker.m.daocloud.io/library/python:3.12-slim
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

# 依赖源可通过 --build-arg PIP_INDEX_URL 替换
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    TZ=Asia/Shanghai \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} uv

# 先只装三方依赖，源码变化不会击穿这层缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --default-index ${PIP_INDEX_URL}

COPY . .

EXPOSE 8000
CMD ["python", "-m", "app.main"]
