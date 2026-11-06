FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 系统依赖：psycopg/asyncpg 编译与健康检查（curl）
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# pip 源可配置：国内网络构建时传 --build-arg PIP_INDEX_URL=<镜像源>
# 例：https://mirrors.cloud.tencent.com/pypi/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 300 -i "${PIP_INDEX_URL}" -r requirements.txt

COPY . .

RUN chmod +x scripts/docker-entrypoint.sh \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 迁移在容器启动前执行（B-703 验收）
ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
