# kis_client/advisor.py

from typing import Dict, Any, List


def generate_advice(result: Dict[str, Any]) -> List[str]:
    """
    evaluate_portfolio() 결과를 바탕으로
    사람이 읽을 수 있는 진단/추천 문장을 리스트로 생성합니다.
    """
    advices: List[str] = []

    positions = result.get("positions", [])
    summary = result.get("summary", {})

    total_pnl_rate = summary.get("total_pnl_rate", 0.0)
    total_value = summary.get("total_value", 0.0)

    # --- 1) 전체 포트폴리오 진단 ---

    # 전체 수익/손실 상황
    if total_pnl_rate > 0.5:
        advices.append(f"현재 포트폴리오는 전체적으로 수익 구간입니다. (약 +{total_pnl_rate:.2f}%)")
    elif total_pnl_rate < -0.5:
        advices.append(f"현재 포트폴리오는 전체적으로 손실 구간입니다. (약 {total_pnl_rate:.2f}%)")
    else:
        advices.append(f"현재 포트폴리오는 큰 수익/손실 없이 거의 횡보 구간입니다. (약 {total_pnl_rate:.2f}%)")

    # 종목 수/분산 정도
    num_positions = len(positions)
    if num_positions == 0:
        advices.append("보유 중인 종목이 없어 평가할 포트폴리오가 없습니다.")
        return advices

    # 최대 비중 종목 찾기
    max_pos = max(positions, key=lambda p: p.get("weight", 0.0))
    max_weight = max_pos.get("weight", 0.0)
    max_name = max_pos.get("name", max_pos.get("symbol"))

    if max_weight >= 70:
        advices.append(
            f"포트폴리오가 [{max_name}] 한 종목에 {max_weight:.1f}% 비중으로 강하게 쏠려 있습니다. "
            f"분산 투자를 고려해보는 것이 좋겠습니다."
        )
    elif max_weight >= 50:
        advices.append(
            f"[{max_name}] 비중이 {max_weight:.1f}%로 비교적 높은 편입니다. "
            f"해당 종목의 리스크를 특히 신경 써서 관리해 주세요."
        )

    if num_positions <= 2 and total_value > 0:
        advices.append(
            f"현재 보유 종목 수가 {num_positions}개로 많지 않아 개별 종목 변동성에 포트폴리오가 민감합니다. "
            f"장기적으로는 3~5개 이상으로 분산하는 것도 고려해보세요."
        )

    # --- 2) 개별 종목 진단 ---

    for pos in positions:
        name = pos.get("name", pos.get("symbol"))
        pnl_rate = pos.get("pnl_rate", 0.0)

        if pnl_rate >= 10:
            advices.append(
                f"[{name}] 수익률이 +{pnl_rate:.2f}%로 높은 편입니다. "
                f"일부 이익 실현(분할 매도)을 고려해볼 만합니다."
            )
        elif pnl_rate <= -5:
            advices.append(
                f"[{name}] 수익률이 {pnl_rate:.2f}%로 손실 구간입니다. "
                f"손절/추가 매수/장기 보유 등 전략을 다시 점검해보는 것이 좋겠습니다."
            )
        elif -1 <= pnl_rate <= 1:
            advices.append(
                f"[{name}]은(는) 아직 수익/손실이 크지 않은 구간입니다 (약 {pnl_rate:.2f}%). "
                f"추가 매수나 매도보다는 추세를 조금 더 지켜보는 것도 한 방법입니다."
            )

    return advices
