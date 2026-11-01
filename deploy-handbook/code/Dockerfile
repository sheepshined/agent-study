# Dockerfile —— 多阶段构建（multi-stage build）示范。
# 机制：第一阶段（builder）只负责"装依赖"，第二阶段（runtime）只拷走安装结果——
# pip 缓存、构建工具、锁文件副本都留在第一阶段，不进最终镜像。
# 对纯标准库服务这个拆分收益小，但它的层结构是 GPU 服务的标准姿势（§2.1/§2.3）。

# ---- 第一阶段：builder ----
FROM python:3.13-alpine AS builder
WORKDIR /app
# 依赖文件先单独拷贝：这一层只要 requirements.txt 不变就永远命中缓存，
# 改代码（COPY agent.py）不会触发重装依赖——层缓存（layer cache）的全部价值就在这个顺序。
COPY requirements.txt ./
# mkdir 先行：requirements 为空时 pip 不会创建 --prefix 目录，
# 下一阶段 COPY --from 会因 "/install 不存在" 直接失败（FAQ #1，本机踩过）
RUN mkdir -p /install && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 第二阶段：runtime ----
FROM python:3.13-alpine
WORKDIR /app
# 只搬运安装结果，不搬运 pip 与缓存
COPY --from=builder /install /usr/local
COPY agent.py .
# 非 root 运行：容器逃逸的最后一道减法（对照 security-handbook §3.1 最小权限）
RUN adduser -D appuser
USER appuser
EXPOSE 8000
# 镜像级健康检查：容器编排器（compose/K8s）都读它；liveness 用 /healthz 就够，
# 别把依赖检查塞进 liveness——依赖抖动会引发重启风暴（§9.4 不变量①）。
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
# 显式声明停止信号：docker stop 发 SIGTERM，应用有宽限期做优雅停机
STOPSIGNAL SIGTERM
# -u 关闭 stdout 缓冲：容器里日志必须实时可见，否则 docker logs 迟滞、崩溃现场丢失
CMD ["python", "-u", "agent.py"]
