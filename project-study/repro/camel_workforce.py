"""camel Workforce 最小复现：一个 Workforce 挂两个 ChatAgent worker，
完成一个需要拆解的小任务。改编自官方 examples/workforce/multiple_single_agents.py
（官方默认 openai 平台 + SearchToolkit，本机换 DashScope + 去掉搜索依赖）。
"""
import os

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.societies.workforce import Workforce
from camel.tasks.task import Task
from camel.types import ModelPlatformType


def make_model() -> object:
    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type="qwen-plus",
        url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.environ["DASHSCOPE_API_KEY"],
    )


def main() -> None:
    researcher = ChatAgent(
        system_message="你是调研员，只负责收集事实清单，不做决策。",
        model=make_model(),
    )
    planner = ChatAgent(
        system_message="你是计划者，基于调研结果给出三条建议，简洁输出。",
        model=make_model(),
    )

    workforce = Workforce("旅行规划小队", default_model=make_model())
    workforce.add_single_agent_worker("调研员：收集目的地信息", researcher)
    workforce.add_single_agent_worker("计划者：输出最终建议", planner)

    task = Task(
        content="为周末两天的一日游想一个方案：先收集 2 个候选地点的事实，"
        "再给出最终推荐。要求总共不超过 200 字。",
    )

    result = workforce.process_task(task)
    print("=== 最终结果 ===")
    print(result.result)


if __name__ == "__main__":
    main()
