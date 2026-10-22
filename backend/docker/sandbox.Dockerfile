# 容器隔离执行器镜像。
#
# 用法（在 backend/ 目录下）：
#   docker build -f docker/sandbox.Dockerfile -t parallax-engine-sandbox:local .
# 然后在 .env 里设：
#   PARALLAX_PLATFORM_EXECUTION_MODE=container
#
# 该镜像只用于 `parallax.service.platform_executor` 这个入口：父 Worker 把
# request.json 写进唯一可写的 /work，容器以只读根文件系统、无网络、
# 无 capability、非 root 用户运行，结果写在 /work/result.json。
#
# 为什么先拷全部源码再 `pip install /app`：只拷 `__init__.py` 时构建后端会
# 认为包内没有子模块，装出来的 `parallax` 缺 `service`，入口直接 ModuleNotFound。
# 依赖层因此无法单独复用，这里选正确性而不是缓存命中率。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY parallax /app/parallax
RUN pip install --no-cache-dir /app

# 65534:65534 是 nobody:nogroup；容器内不需要任何特权用户。
USER 65534:65534

WORKDIR /work

ENTRYPOINT ["python", "-m", "parallax.service.platform_executor"]
