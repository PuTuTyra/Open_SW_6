from mcp.server.fastmcp import FastMCP

from kis_client.price import get_domestic_quote
from kis_client.account import get_mock_account_positions
from kis_client.service import analyze_mock_portfolio

mcp = FastMCP(
    "kis-mock-portfolio",
    json_response=True,
    # 이건 있어도 되고 없어도 되지만, 넣어두면 uv가 알아서 설치해줍니다.
    dependencies=[
        "pycryptodomex",
        "pandas",
        "requests",
        "websockets",
        "pyyaml",
    ],
)


@mcp.tool()
def domestic_quote(symbol: str) -> dict:
    """국내 주식/ETF 한 종목의 현재 시세를 조회합니다."""
    return get_domestic_quote(symbol)


@mcp.tool()
def mock_portfolio_positions() -> list[dict]:
    """모의투자 국내 주식 계좌의 보유 종목 리스트를 반환합니다."""
    return get_mock_account_positions()


@mcp.tool()
def mock_portfolio_overview() -> dict:
    """모의투자 계좌 전체를 평가한 결과(포지션 + 요약)를 반환합니다."""
    data = analyze_mock_portfolio()
    return {
        "positions": data["positions"],
        "summary": data["summary"],
    }


@mcp.tool()
def mock_portfolio_advice() -> dict:
    """모의투자 계좌 평가 + 한국어 진단/추천 코멘트를 함께 반환합니다."""
    return analyze_mock_portfolio()

if __name__ == "__main__":
    import sys
    print("🚀 MCP 서버 시작: kis-mock-portfolio (stdio 대기 중)", file=sys.stderr)
    mcp.run(transport="stdio")
