# web_service.py

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp_client_utils import call_mcp_tool_json
from fastapi.staticfiles import StaticFiles


app = FastAPI(
    title="KIS Mock Portfolio Service (via MCP)",
    description="KIS 오픈API 모의투자 계좌를 MCP 서버로 감싸고, FastAPI로 HTTP 서비스로 제공합니다.",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------- 응답 모델 (선택: 문서용 / 타입 안정성용) ----------

class Position(BaseModel):
    symbol: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    market: str | None = None
    sector: str | None = None
    cost: float
    value: float
    pnl: float
    pnl_rate: float
    weight: float


class PortfolioSummary(BaseModel):
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_rate: float


class PortfolioOverviewResponse(BaseModel):
    positions: list[Position]
    summary: PortfolioSummary


class PortfolioAdviceResponse(PortfolioOverviewResponse):
    advices: list[str] | None = None


class QuoteResponse(BaseModel):
    symbol: str
    name: str | None = None
    price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    change: float | None = None
    change_rate: float | None = None
    # 필요하면 필드 자유롭게 추가 가능


# ---------- 엔드포인트 정의 ----------

@app.get("/portfolio/overview", response_model=PortfolioOverviewResponse)
async def get_portfolio_overview() -> Dict[str, Any]:
    """
    모의투자 계좌 전체 요약 (포지션 + 요약 수치)
    MCP 툴: mock_portfolio_overview
    """
    data = await call_mcp_tool_json("mock_portfolio_overview", {})
    return data


@app.get("/portfolio/advice", response_model=PortfolioAdviceResponse)
async def get_portfolio_advice() -> Dict[str, Any]:
    """
    모의투자 계좌 요약 + 한국어 진단/추천 코멘트
    MCP 툴: mock_portfolio_advice
    """
    data = await call_mcp_tool_json("mock_portfolio_advice", {})
    return data


@app.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(symbol: str) -> Dict[str, Any]:
    """
    단일 종목 현재 시세 조회
    MCP 툴: domestic_quote
    """
    if len(symbol) != 6 or not symbol.isdigit():
        raise HTTPException(status_code=400, detail="종목 코드는 6자리 숫자로 입력해야 합니다.")

    data = await call_mcp_tool_json("domestic_quote", {"symbol": symbol})
    # 최소한 symbol은 항상 채워주도록 보정
    data.setdefault("symbol", symbol)
    return data


@app.get("/")
async def root():
    return {
        "message": "KIS Mock Portfolio Service (via MCP)",
        "endpoints": [
            "/portfolio/overview",
            "/portfolio/advice",
            "/quote/{symbol}",
            "/docs",
        ],
    }
