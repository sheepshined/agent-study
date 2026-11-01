"""browser-use 最小复现：ChatDeepSeek(deepseek-chat) + 本机 Chromium。
改编自官方 examples/simple.py——官方默认 ChatBrowserUse 云端模型（需付费
BROWSER_USE_API_KEY），本机换成原生 DeepSeek provider + 文本模式(use_vision=False)。
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek


async def main() -> None:
    llm = ChatDeepSeek(model='deepseek-chat', temperature=0.0)
    agent = Agent(
        task='打开 https://example.com ，读取页面主标题(h1)文本，用 done 动作返回它。',
        llm=llm,
        use_vision=False,
    )
    history = await agent.run(max_steps=5)
    print('=== 最终结果 ===')
    print(history.final_result())
    print('=== 实际步数 ===', len(history.history))


if __name__ == '__main__':
    asyncio.run(main())
