"""crewAI 最小复现：两 Agent 顺序 Crew + 自定义工具。
模型走 DashScope OpenAI 兼容端点（环境变量 OPENAI_API_BASE/OPENAI_API_KEY）。
改编自官方 README 快速开始示例。
"""
import os

from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = "精确计算两个整数的和，参数 a 与 b。"

    def _run(self, a: int, b: int) -> int:
        return a + b


def main() -> None:
    researcher = Agent(
        role="资深数据研究员",
        goal="用提供的工具算出准确数字",
        backstory="你以精确著称，算术必须用工具完成。",
        tools=[CalculatorTool()],
        verbose=True,
        llm="glm-4-flash",
    )
    writer = Agent(
        role="报告撰写人",
        goal="把研究结论整理成一句话结论",
        backstory="你擅长把复杂数据写成一句人话。",
        verbose=True,
        llm="glm-4-flash",
    )

    t1 = Task(
        description="计算 17 加 25 的结果并报出数字。",
        expected_output="一行：计算结果。",
        agent=researcher,
    )
    t2 = Task(
        description="基于上一任务结果，写出一句面向管理层的中文结论。",
        expected_output="一句话中文结论。",
        agent=writer,
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[t1, t2],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    print("=== 最终输出 ===")
    print(result.raw)


if __name__ == "__main__":
    main()
