import asyncio
import sys
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_tool_json(session: ClientSession, name: str, arguments: dict) -> dict:
    """MCP 툴을 호출하고, content[0].text에 있는 JSON을 dict로 파싱해서 반환."""
    result = await session.call_tool(name, arguments)
    text = result.content[0].text
    return json.loads(text)


async def show_overview(session: ClientSession) -> None:
    """모의투자 계좌 요약 리포트 출력."""
    data = await call_tool_json(session, "mock_portfolio_overview", {})

    summary = data["summary"]
    positions = data["positions"]

    print("\n=== [모의투자 계좌 요약] ===")
    print(f"총 매수금액 : {summary['total_cost']:.0f}원")
    print(f"총 평가금액 : {summary['total_value']:.0f}원")
    print(f"총 손익     : {summary['total_pnl']:.0f}원")
    print(f"총 수익률   : {summary['total_pnl_rate']:.2f}%")

    print("\n[보유 종목]")
    for pos in positions:
        print(
            f"- {pos['name']}({pos['symbol']}), "
            f"수량 {pos['quantity']}주, "
            f"평단 {pos['avg_price']:.0f}원, "
            f"현재가 {pos['current_price']:.0f}원, "
            f"손익 {pos['pnl']:.0f}원 ({pos['pnl_rate']:.2f}%), "
            f"비중 {pos['weight']:.2f}%"
        )
    print()


async def show_advice(session: ClientSession) -> None:
    """모의투자 계좌 진단/추천 코멘트 출력."""
    data = await call_tool_json(session, "mock_portfolio_advice", {})

    summary = data["summary"]
    advices = data.get("advices", [])

    print("\n=== [모의투자 계좌 진단] ===")
    print(f"총 손익   : {summary['total_pnl']:.0f}원")
    print(f"총 수익률 : {summary['total_pnl_rate']:.2f}%\n")

    print("[진단 및 추천]")
    if not advices:
        print("- (코멘트 없음)")
    else:
        for i, line in enumerate(advices, start=1):
            print(f"{i}. {line}")
    print()


async def show_quote(session: ClientSession) -> None:
    """단일 종목 현재가 조회."""
    symbol = input("\n조회할 종목 코드 6자리 (예: 000660): ").strip()
    if not symbol:
        print("종목 코드를 입력하지 않아 취소되었습니다.\n")
        return

    try:
        data = await call_tool_json(session, "domestic_quote", {"symbol": symbol})
    except Exception as e:
        print(f"시세 조회 중 오류가 발생했습니다: {e}\n")
        return

    # 어떤 필드가 올지 모를 수 있으니 .get()으로 안전하게 접근
    name = data.get("name", "(이름 없음)")
    price = data.get("price")
    open_ = data.get("open")
    high = data.get("high")
    low = data.get("low")
    change = data.get("change")
    change_rate = data.get("change_rate")

    print("\n=== [단일 종목 시세] ===")
    print(f"종목명   : {name} ({symbol})")
    if price is not None:
        print(f"현재가   : {price:.0f}원")
    if open_ is not None:
        print(f"시가     : {open_:.0f}원")
    if high is not None and low is not None:
        print(f"고가/저가 : {high:.0f}원 / {low:.0f}원")
    if change is not None and change_rate is not None:
        print(f"전일대비 : {change:.0f}원 ({change_rate:.2f}%)")
    print()


async def main():
    project_root = Path(__file__).parent

    server_params = StdioServerParameters(
        command=sys.executable,                          # 지금 venv 파이썬 그대로 사용
        args=[str(project_root / "mcp_server.py")],      # MCP 서버 스크립트
        cwd=str(project_root),
    )

    # MCP 서버를 서브프로세스로 띄우고, 세션을 유지한 채로 메뉴 루프
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("\n=== KIS 모의투자 포트폴리오 CLI (MCP) ===")

            while True:
                print("\n[메뉴]")
                print("1. 계좌 요약 보기")
                print("2. 계좌 진단/추천 코멘트 보기")
                print("3. 단일 종목 현재가 조회")
                print("4. 종료")

                choice = input("메뉴 번호를 선택하세요: ").strip()

                if choice == "1":
                    await show_overview(session)
                elif choice == "2":
                    await show_advice(session)
                elif choice == "3":
                    await show_quote(session)
                elif choice in ("4", "q", "Q", "exit", "quit"):
                    print("프로그램을 종료합니다.")
                    break
                else:
                    print("잘못된 입력입니다. 1~4 중에서 선택해 주세요.")


if __name__ == "__main__":
    asyncio.run(main())