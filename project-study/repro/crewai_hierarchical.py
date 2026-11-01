"""crewAI hierarchical 过程最小复现：manager 自动委派两个 worker。
验证 _run_hierarchical_process（crew.py:1526）→ DelegateWork/AskQuestion 工具链。
"""
from crewai import Agent, Crew, Process, Task


def main() -> None:
    worker_a = Agent(
        role="事实核查员",
        goal="核对数字",
        backstory="你只报告事实。",
        llm="glm-4-flash",
    )
    worker_b = Agent(
        role="文案",
        goal="写一句结论",
        backstory="你擅长一句话总结。",
        llm="glm-4-flash",
    )

    t1 = Task(description="中国国土面积约是多少万平方公里？", expected_output="一个数字。")
    t2 = Task(description="基于事实核查结果，写一句介绍中国国土面积的中文。", expected_output="一句话。")

    crew = Crew(
        agents=[worker_a, worker_b],
        tasks=[t1, t2],
        process=Process.hierarchical,
        manager_llm="glm-4-flash",
        verbose=False,
    )
    result = crew.kickoff()
    print("=== 最终输出 ===")
    print(result.raw)


if __name__ == "__main__":
    main()
