# kis_client/account.py

"""
모의투자 국내 주식 계좌의 보유 종목을 가져와서
portfolio.evaluate_portfolio()에서 쓸 수 있는 형태로 변환하는 모듈
"""

import os
import sys
from typing import List, Dict, Any

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
EXAMPLES_USER = os.path.join(REPO_ROOT, "examples_user")
DOMESTIC_STOCK = os.path.join(EXAMPLES_USER, "domestic_stock")

for p in [EXAMPLES_USER, DOMESTIC_STOCK]:
    if p not in sys.path:
        sys.path.append(p)

import kis_auth as ka
from domestic_stock_functions import inquire_balance


def _to_float(val) -> float:
    try:
        if val is None:
            return 0.0
        return float(str(val).replace(",", ""))
    except Exception:
        return 0.0


def get_mock_account_positions() -> List[Dict[str, Any]]:
    """
    모의투자 국내 주식 계좌의 '보유 종목'을 조회해서

    [
        {"symbol": "000660", "quantity": 1.0, "avg_price": 540000.0},
        ...
    ]

    형태의 리스트로 반환합니다.
    보유 종목이 없다면 [] 를 반환합니다.
    """
    # 1) 인증 (모의투자)
    ka.auth(svr="vps", product=ka._cfg["my_prod"])

    env = "demo"
    cano = ka._cfg.get("my_paper_stock")
    acnt_prdt_cd = ka._cfg.get("my_prod")

    # 2) 잔고/보유 종목 조회
    df1, df2 = inquire_balance(
        env_dv=env,
        cano=cano,
        acnt_prdt_cd=acnt_prdt_cd,
        afhr_flpr_yn="N",
        inqr_dvsn="01",
        unpr_dvsn="01",
        fund_sttl_icld_yn="N",
        fncg_amt_auto_rdpt_yn="N",
        prcs_dvsn="01",
    )

    positions: List[Dict[str, Any]] = []

    if df1 is None or df1.empty:
        return positions

    # df1의 컬럼은 방금 학습자님이 보여준 dict 기준:
    # pdno, hldg_qty, pchs_avg_pric ...
    for _, row in df1.iterrows():
        symbol = str(row.get("pdno", "")).zfill(6)
        quantity = _to_float(row.get("hldg_qty", 0))
        avg_price = _to_float(row.get("pchs_avg_pric", 0))

        if not symbol:
            continue

        positions.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": avg_price,
            }
        )

    return positions


if __name__ == "__main__":
    positions = get_mock_account_positions()
    print("=== get_mock_account_positions() 결과 ===")
    for p in positions:
        print(p)
