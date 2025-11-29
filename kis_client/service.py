# kis_client/service.py

from .account import get_mock_account_positions
from .portfolio import evaluate_portfolio
from .advisor import generate_advice

def analyze_mock_portfolio():
    """
    모의투자 국내 주식 계좌 전체를 평가하고,
    평가 결과 + 한국어 진단 코멘트를 함께 반환.
    """
    positions = get_mock_account_positions()
    if not positions:
        return {
            "positions": [],
            "summary": None,
            "advices": ["보유 중인 종목이 없습니다. (모의투자 계좌에 매수한 종목이 있어야 합니다.)"],
        }

    result = evaluate_portfolio(positions)
    advices = generate_advice(result)

    return {
        "positions": result["positions"],
        "summary": result["summary"],
        "advices": advices,
    }

if __name__ == "__main__":
    from pprint import pprint

    result = analyze_mock_portfolio()

    print("\n[요약]")
    pprint(result["summary"])

    print("\n[종목별 평가]")
    for pos in result["positions"]:
        pprint(pos)

    print("\n[진단/코멘트]")
    for adv in result["advices"]:
        print("-", adv)
