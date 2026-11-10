FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 系统依赖：psycopg/asyncpg 编译、健康检查（curl）、音视频转写（ffmpeg/ffprobe）
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# pip 源可配置：国内网络构建时传 --build-arg PIP_INDEX_URL=<镜像源>
# 默认走腾讯云镜像：直连 pypi.org 在国内实测约 20 kB/s（torch 539MB 要数小时），
# 换镜像后同一台机器可在数分钟内完成。海外构建可显式传 --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
# 可选：先装 CPU 版 torch（云端 2G 精简镜像推荐），避免 requirements 拉取 CUDA 版
# 例：--build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_INDEX_URL=
RUN if [ -n "${TORCH_INDEX_URL}" ]; then \
      pip install --no-cache-dir --index-url "${TORCH_INDEX_URL}" torch; \
    fi
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 10 --timeout 300 -i "${PIP_INDEX_URL}" -r requirements.txt

# ---- embedding 模型离线化：构建时下载（约 470MB），运行时不再联网 ----
# 国内构建可传 --build-arg HF_ENDPOINT=https://hf-mirror.com
ARG HF_ENDPOINT=https://hf-mirror.com
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ARG EMBEDDING_PRELOAD=true
ENV EMBEDDING_CACHE_DIR=/app/.models
RUN if [ "$EMBEDDING_PRELOAD" = "true" ]; then \
      HF_ENDPOINT="${HF_ENDPOINT}" EMBEDDING_MODEL="${EMBEDDING_MODEL}" python -c "\
import os; \
from sentence_transformers import SentenceTransformer; \
SentenceTransformer(os.environ['EMBEDDING_MODEL'], cache_folder='/app/.models')"; \
    fi
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    OMP_NUM_THREADS=1

COPY . .

RUN chmod +x scripts/docker-entrypoint.sh \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 迁移在容器启动前执行（B-703 验收）
ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
