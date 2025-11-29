import time
from typing import List, Dict, Any

from .price import get_domestic_quote


def evaluate_position(position: Dict[str, Any]) -> Dict[str, Any]:
    """
    단일 국내 종목 포지션을 평가합니다.
    position 예시:
        { "symbol": "000660", "quantity": 1, "avg_price": 540000 }
    """
    symbol = position["symbol"]
    quantity = float(position["quantity"])
    avg_price = float(position["avg_price"])

    # 1) 현재 시세 조회
    quote = get_domestic_quote(symbol)

    current_price = float(quote["price"])
    market = quote.get("market")
    sector = quote.get("sector")
    name = quote.get("name", symbol)

    # 2) 금액 계산
    cost = avg_price * quantity              # 매수금액
    value = current_price * quantity         # 평가금액
    pnl = value - cost                       # 평가손익
    pnl_rate = (pnl / cost * 100) if cost != 0 else 0.0

    result = {
        "symbol": symbol,
        "name": name,
        "quantity": quantity,
        "avg_price": avg_price,
        "current_price": current_price,
        "market": market,
        "sector": sector,
        "cost": cost,
        "value": value,
        "pnl": pnl,
        "pnl_rate": pnl_rate,
        "weight": None,   # 포트폴리오 전체 평가에서 채움
    }

    return result


def evaluate_portfolio(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    evaluated_positions: List[Dict[str, Any]] = []

    for pos in positions:
        symbol = pos.get("symbol")
        try:
            evaluated = evaluate_position(pos)
            evaluated_positions.append(evaluated)
        except ValueError as e:
            print(f"[경고] {symbol} 평가 중 오류 발생, 이 종목은 스킵합니다: {e}")
        except Exception as e:
            print(f"[경고] {symbol} 평가 중 예상치 못한 오류, 스킵합니다: {e}")
        finally:
            time.sleep(0.3)  # 다음 TR까지 텀 조금 주기

    if not evaluated_positions:
        return {
            "positions": [],
            "summary": {
                "total_cost": 0.0,
                "total_value": 0.0,
                "total_pnl": 0.0,
                "total_pnl_rate": 0.0,
            },
        }

    # 아래는 그대로 (합계/비중 계산)
    total_cost = sum(p["cost"] for p in evaluated_positions)
    total_value = sum(p["value"] for p in evaluated_positions)
    total_pnl = total_value - total_cost
    total_pnl_rate = (total_pnl / total_cost * 100) if total_cost != 0 else 0.0

    for p in evaluated_positions:
        if total_value > 0:
            p["weight"] = p["value"] / total_value * 100
        else:
            p["weight"] = 0.0

    summary = {
        "total_cost": total_cost,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_rate": total_pnl_rate,
    }

    return {
        "positions": evaluated_positions,
        "summary": summary,
    }