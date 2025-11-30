import asyncio
import sys
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    project_root = Path(__file__).parent

    server_params = StdioServerParameters(
        command=sys.executable,                         # venv 파이썬 그대로 사용
        args=[str(project_root / "mcp_server.py")],
        cwd=str(project_root),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) 툴 목록 출력
            tools_response = await session.list_tools()
            print("=== MCP tools ===")
            for tool in tools_response.tools:
                print(f"- {tool.name} : {tool.description}")

            # 2) mock_portfolio_overview 호출
            result = await session.call_tool(
                "mock_portfolio_overview",
                arguments={},
            )

            print("\n=== RAW result ===")
            print(result)

            # 3) content[0].text 안에 있는 JSON 문자열 파싱
            text_content = result.content[0].text
            data = json.loads(text_content)

            print("\n=== Parsed portfolio overview ===")
            print(f"총 매수금액: {data['summary']['total_cost']:.0f}원")
            print(f"총 평가금액: {data['summary']['total_value']:.0f}원")
            print(f"총 손익: {data['summary']['total_pnl']:.0f}원")
            print(f"총 수익률: {data['summary']['total_pnl_rate']:.2f}%")

            print("\n[보유 종목]")
            for pos in data["positions"]:
                print(
                    f"- {pos['name']}({pos['symbol']}), "
                    f"수량 {pos['quantity']}주, "
                    f"평단 {pos['avg_price']:.0f}원, "
                    f"현재가 {pos['current_price']:.0f}원, "
                    f"손익 {pos['pnl']:.0f}원 ({pos['pnl_rate']:.2f}%), "
                    f"비중 {pos['weight']:.2f}%"
                )
            
            # 4) mock_portfolio_advice 호출 (한국어 코멘트)
            advice_result = await session.call_tool(
                "mock_portfolio_advice",
                arguments={},
            )

            advice_text = advice_result.content[0].text
            print("\n=== Portfolio Advice (from MCP) ===")
            print(advice_text)


if __name__ == "__main__":
    asyncio.run(main())
