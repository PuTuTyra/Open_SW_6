# kis_client/run_analysis.py

from .account import get_mock_account_positions
from .portfolio import evaluate_portfolio
from .advisor import generate_advice


def main():
    positions = get_mock_account_positions()
    print("=== 계좌에서 불러온 positions ===")
    print(positions)

    if not positions:
        print("보유 종목이 없습니다. (모의투자 계좌에 매수한 종목이 있어야 합니다.)")
        return

    result = evaluate_portfolio(positions)

    print("\n=== 개별 종목 평가 결과 ===")
    for pos in result["positions"]:
        print(
            f"[{pos['symbol']} {pos['name']}] "
            f"수량: {pos['quantity']}, 평단: {pos['avg_price']:.0f}, "
            f"현재가: {pos['current_price']:.0f}, "
            f"평가금액: {pos['value']:.0f}, 손익: {pos['pnl']:.0f} "
            f"({pos['pnl_rate']:.2f}%), 비중: {pos['weight']:.2f}%"
        )

    print("\n=== 포트폴리오 요약 ===")
    s = result["summary"]
    print(f"총 매수금액: {s['total_cost']:.0f}")
    print(f"총 평가금액: {s['total_value']:.0f}")
    print(f"총 손익: {s['total_pnl']:.0f} ({s['total_pnl_rate']:.2f}%)")

# 🔹 여기서 진단/추천 출력
    print("\n=== 진단 & 추천 코멘트 ===")
    advices = generate_advice(result)
    for line in advices:
        print(f"- {line}")
        
if __name__ == "__main__":
    main()
