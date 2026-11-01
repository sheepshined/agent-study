"""camel 最小复现：ChatAgent + 工具 + DashScope(qwen-plus, OpenAI 兼容端点)。
对应官方最小示例 examples/agents/create_chat_agent.py 的变体（官方默认 openai 平台，
本机只有 DASHSCOPE_API_KEY，故走 ModelPlatformType.OPENAI_COMPATIBLE_MODEL）。
"""
import os

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.toolkits import FunctionTool
from camel.types import ModelPlatformType


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def main() -> None:
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type="qwen-plus",
        url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.environ["DASHSCOPE_API_KEY"],
    )
    agent = ChatAgent(
        system_message="你是精确计算助手，算术必须调用工具完成。",
        model=model,
        tools=[FunctionTool(add)],
    )
    resp = agent.step("请计算 17 加 25 等于多少？")
    print("=== 最终回答 ===")
    print(resp.msgs[0].content)
    print("=== 工具调用记录 ===")
    for rec in resp.info.get("tool_calls", []):
        print(rec)


if __name__ == "__main__":
    main()
