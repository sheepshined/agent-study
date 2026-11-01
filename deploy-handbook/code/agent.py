# agent.py —— 最小可部署的推理/agent 服务（纯 Python 标准库，无第三方依赖）。
#
# 演示目标：一个"能上生产"的模型服务，拆开看只有六件事——
#   ① 两层健康检查（liveness / readiness，作用不同，不可混用）
#   ② /metrics 暴露 Prometheus 文本格式指标（可观测是部署的一部分，不是附加品）
#   ③ 预算熔断（在读到请求体之后、调用"模型"之前，便宜的地方先挡）
#   ④ 日志 PII 脱敏（进日志的每条消息都过同一个函数）
#   ⑤ 优雅停机（SIGTERM → 停止接新请求 → 等在途请求收尾）
#   ⑥ 计量进指标而不是只进日志（指标可告警，日志只可翻阅）
#
# 运行：python agent.py   （默认 0.0.0.0:8000；容器内由 CMD 指定 -u 无缓冲输出）

import json
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("AGENT_PORT", "8000"))
WARMUP_SECONDS = float(os.environ.get("AGENT_WARMUP_SECONDS", "3"))
MAX_COMPLETION_TOKENS = int(os.environ.get("AGENT_MAX_COMPLETION_TOKENS", "512"))

# 假装的价格表（美元 / token）。换真模型时换成真实价目表即可，
# 成本口径与 tuning-handbook §7.1 的"四档单价"一致：输入贵 1x、输出贵 4x。
PRICE_PER_TOKEN = {"input": 0.000001, "output": 0.000004}

# ---------------------------------------------------------------- 指标注册表
# 不变量：/metrics 是纯文本协议，类型只有 counter/gauge/histogram/summary 四种；
# histogram 必须同时给出 _bucket/_sum/_count 三组样本，缺一组 PromQL 就算不出分位数。


class Counter:
    """只增不减的计数器（counter）。并发下用锁保证 inc 原子。"""

    def __init__(self, name, help_text, label_names=()):
        self.name, self.help, self.label_names = name, help_text, label_names
        self.values = {}  # label 值元组 -> 数值
        self.lock = threading.Lock()

    def inc(self, value=1.0, **labels):
        key = tuple(labels.get(n, "") for n in self.label_names)
        with self.lock:
            self.values[key] = self.values.get(key, 0.0) + value

    def render(self):
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        for key, val in sorted(self.values.items()):
            label = "".join(f'{n}="{v}",' for n, v in zip(self.label_names, key))
            lines.append(f"{self.name}{{{label}}} {val}")
        return lines


class Gauge:
    """可增可减的瞬时值（gauge）：只保留最后一次 set 的值。"""

    def __init__(self, name, help_text):
        self.name, self.help = name, help_text
        self.value = 0.0
        self.lock = threading.Lock()

    def set(self, value):
        with self.lock:
            self.value = value

    def render(self):
        return [
            f"# HELP {self.name} {self.help}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {self.value}",
        ]


class Histogram:
    """分桶直方图（histogram）：桶边界固定、提前写死。
    不变量：桶边界是部署决策的一部分——桶选错（比如全部落在第一桶），
    分位数就失去分辨率；改桶要和改告警阈值一起评审。"""

    BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))

    def __init__(self, name, help_text):
        self.name, self.help = name, help_text
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.counts = [0] * len(self.BUCKETS)
        self.total, self.count = 0.0, 0

    def observe(self, value):
        with self.lock:
            for i, bound in enumerate(self.BUCKETS):
                if value <= bound:
                    self.counts[i] += 1
            self.total += value
            self.count += 1

    def render(self):
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self.lock:
            cumulative = 0
            for bound, cnt in zip(self.BUCKETS, self.counts):
                cumulative += cnt
                le = "+Inf" if bound == float("inf") else f"{bound}"
                lines.append(f'{self.name}_bucket{{le="{le}"}} {cumulative}')
            lines.append(f"{self.name}_sum {self.total}")
            lines.append(f"{self.name}_count {self.count}")
        return lines


REQ_TOTAL = Counter("http_requests_total", "请求数（按路由与状态码）", ("route", "code"))
DURATION = Histogram("http_request_duration_seconds", "请求处理耗时（秒）")
TTFT = Histogram("agent_ttft_seconds", "首 token 延迟 TTFT（秒）")
# 同名指标只能出现一组 HELP/TYPE 行——输入/输出共用一个 counter，用 direction 标签区分；
# 同名重复注册会让 Prometheus 整次抓取报错（duplicate HELP），这是文本协议最常踩的坑。
TOKENS = Counter("agent_tokens_total", "token 数（输入/输出）", ("direction",))
COST = Counter("agent_cost_usd_total", "累计成本（美元）")
MODEL_READY = Gauge("agent_model_ready", "模型就绪标志：1=可接流量 0=预热中")

# ---------------------------------------------------------------- 服务逻辑


def mask_pii(text: str) -> str:
    """PII 脱敏：手机号/长数字串打码、邮箱替换。
    不变量：脱敏发生在"打印之前"，日志函数是唯一出口——
    绕过这个函数直接 print，防线就漏了（security-handbook §4.1 的出口过滤）。"""
    text = re.sub(r"\d{5,}", "****", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    return text


def fake_model_call(message: str) -> dict:
    """模拟一次模型推理：prefill（输入）+ decode（逐 token 输出）。
    真实推理引擎的耗时形态就是"首 token 慢于后续"——
    vLLM/SGLang 的连续批处理决定 TTFT，输出速率由 decode 决定（§3.1）。"""
    prompt_tokens = max(1, len(message) // 2)  # 中文近似 1 token ≈ 2 字符
    completion_tokens = min(MAX_COMPLETION_TOKENS, max(8, prompt_tokens // 2 + 8))

    prefill = 0.02 + prompt_tokens * 0.0002  # 首字延迟：随上下文变长
    time.sleep(prefill)
    ttft = prefill
    time.sleep(completion_tokens * 0.003)  # decode：逐 token 生成

    cost = prompt_tokens * PRICE_PER_TOKEN["input"] + completion_tokens * PRICE_PER_TOKEN["output"]
    TOKENS.inc(prompt_tokens, direction="input")
    TOKENS.inc(completion_tokens, direction="output")
    COST.inc(cost)
    TTFT.observe(ttft)
    return {
        "reply": f"[示例回复] 已收到：{mask_pii(message[:40])}……（模拟 {completion_tokens} 个输出 token）",
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        "cost_usd": round(cost, 8),
        "ttft_seconds": round(ttft, 4),
    }


def warmup():
    """预热：真实服务里是"加载权重/建连接/编译图"。
    在此之前 /readyz 返回 503，编排器把流量摘走——
    这是 readiness 与 liveness 分层的全部意义（§9.4 不变量①）。"""
    time.sleep(WARMUP_SECONDS)
    MODEL_READY.set(1)
    print(json.dumps({"ts": time.time(), "event": "ready", "warmup_s": WARMUP_SECONDS}), flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # 保持长连接，压测器/网关都受益

    def _send(self, code: int, body: str, content_type="text/plain; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":  # liveness：进程活着就回 200，不做任何依赖检查
            self._send(200, "ok")
            REQ_TOTAL.inc(route="/healthz", code=200)
        elif self.path == "/readyz":  # readiness：依赖没好就 503，让负载均衡摘流量
            ready = MODEL_READY.value >= 1
            self._send(200 if ready else 503, "ready" if ready else "warming up")
            REQ_TOTAL.inc(route="/readyz", code=200 if ready else 503)
        elif self.path == "/metrics":
            lines = []
            for collector in (REQ_TOTAL, DURATION, TTFT, TOKENS, COST, MODEL_READY):
                lines.extend(collector.render())
            lines.append("")  # 文本格式以空行结尾
            self._send(200, "\n".join(lines), "text/plain; version=0.0.4")
            REQ_TOTAL.inc(route="/metrics", code=200)
        else:
            self._send(404, "not found")
            REQ_TOTAL.inc(route="other", code=404)

    def do_POST(self):
        if self.path != "/chat":
            self._send(404, "not found")
            REQ_TOTAL.inc(route="other", code=404)
            return
        start = time.time()
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            message = str(payload.get("message", ""))[:4000]
            asked = int(payload.get("max_tokens", MAX_COMPLETION_TOKENS))
            # 预算熔断：在"调用模型"之前挡掉必赔的请求（F6 成本失控的第一道闸）。
            if asked > MAX_COMPLETION_TOKENS:
                self._send(400, json.dumps({"error": f"max_tokens 超过服务上限 {MAX_COMPLETION_TOKENS}"}, ensure_ascii=False))
                REQ_TOTAL.inc(route="/chat", code=400)
                return
            if not message:
                self._send(400, json.dumps({"error": "message 为空"}, ensure_ascii=False))
                REQ_TOTAL.inc(route="/chat", code=400)
                return
            result = fake_model_call(message)
            self._send(200, json.dumps(result, ensure_ascii=False), "application/json; charset=utf-8")
            REQ_TOTAL.inc(route="/chat", code=200)
            DURATION.observe(time.time() - start)
        except Exception as exc:  # 防御：任何异常都变 500 + 指标，不让线程死掉
            print(json.dumps({"ts": time.time(), "event": "error", "err": str(exc)}), flush=True)
            self._send(500, json.dumps({"error": "internal"}))
            REQ_TOTAL.inc(route="/chat", code=500)

    def log_message(self, fmt, *args):  # 默认的逐请求 stderr 日志换成结构化 JSON 一行
        print(json.dumps({"ts": time.time(), "event": "access", "msg": mask_pii(fmt % args)}), flush=True)


server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)


def shutdown(signum, frame):
    """优雅停机：SIGTERM（docker stop 的默认信号）→ 停止接新请求 → 主线程 join。
    不变量：宽限期（compose 里默认 10s）内必须退完，退不完才被 SIGKILL——
    所以在途请求的处理时间要 < 宽限期，这是容量规划的一部分（§6.5）。"""
    print(json.dumps({"ts": time.time(), "event": "shutdown", "signal": signum}), flush=True)
    threading.Thread(target=server.shutdown, daemon=True).start()


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

if __name__ == "__main__":
    print(json.dumps({"ts": time.time(), "event": "start", "port": PORT}), flush=True)
    threading.Thread(target=warmup, daemon=True).start()
    server.serve_forever()  # 阻塞直到 shutdown() 被调用
    server.server_close()
