# 多阶段构建：builder 装依赖，runtime 只带运行时产物，镜像更小且不含编译工具链。
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY parallax ./parallax

RUN pip install --prefix=/install .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PARALLAX_RUNS_DIR=/data/runs

# 非 root 运行：审查任务会读取挂载进来的代码仓库，容器不应有写系统目录的能力
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin parallax \
    && mkdir -p /data/runs \
    && chown -R parallax:parallax /data

COPY --from=builder /install /usr/local

USER parallax
WORKDIR /home/parallax

EXPOSE 8000

# 探针直接打 /health，而不是只看进程在不在——进程活着但服务卡死同样应当被判为不健康
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "parallax.service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
