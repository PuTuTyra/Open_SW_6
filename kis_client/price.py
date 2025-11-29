# kis_client/price.py

"""
KIS 오픈소스를 직접 쓰기 불편하니까,
우리 서비스에서 쓰기 편하게 감싸주는 '시세 조회 모듈'

- 국내 주식/ETF 현재가 조회: get_domestic_quote()
"""

import os
import sys
import time
from typing import Dict, Any
from .code_name_map import CODE_NAME_MAP

import pandas as pd

# --- 경로 설정: examples_user / domestic_stock 쪽 모듈을 쓸 수 있게 sys.path 추가 ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))           # kis_client 폴더 경로
REPO_ROOT = os.path.dirname(BASE_DIR)                           # open-trading-api 루트
EXAMPLES_USER = os.path.join(REPO_ROOT, "examples_user")
DOMESTIC_STOCK = os.path.join(EXAMPLES_USER, "domestic_stock")

for p in [EXAMPLES_USER, DOMESTIC_STOCK]:
    if p not in sys.path:
        sys.path.append(p)

# 이제 kis_auth, domestic_stock_functions를 import 할 수 있게 됨
import kis_auth as ka
from domestic_stock_functions import inquire_price


# --- 내부 helper: 인증 보장용 함수 ---

def _ensure_auth() -> None:
    """
    인증이 안 돼 있으면 토큰을 발급해주는 함수.
    모의투자(vps) 기준으로 동작.
    """
    # 모의투자 서버: svr="vps"
    # product: 계좌 뒤 2자리 (보통 "01")
    ka.auth(svr="vps", product=ka._cfg["my_prod"])


# --- 실제로 우리가 쓸 함수: 국내 주식/ETF 시세 조회 ---

def get_domestic_quote(symbol: str, retry: int = 1) -> Dict[str, Any]:
    """
    국내 주식/ETF 한 종목의 현재 시세를 조회해서
    우리 서비스에서 쓰기 쉬운 dict 형태로 반환.

    예:
        data = get_domestic_quote("005930")
        print(data["price"])

    반환 예시(dict):
    {
        "symbol": "005930",
        "name": "삼성전자",
        "price": 102800.0,
        "open": 100500.0,
        "high": 102900.0,
        "low": 99300.0,
        "change": 3500.0,
        "change_rate": 3.52,
        "volume": 21274039,
        "market": "KOSPI200",
        "sector": "전기·전자",
    }
    """
    # 1) 인증 보장
    _ensure_auth()

    # 2) KIS 함수 호출 (모의투자 → env_dv="demo")
    df: pd.DataFrame = inquire_price(
        env_dv="demo",
        fid_cond_mrkt_div_code="J",  # 주식(코스피/코스닥) 시장
        fid_input_iscd=symbol        # 단축코드(예: "005930")
    )

    # 레이트 리밋 등으로 인해 빈 결과가 올 수 있으니 한 번 정도 재시도
    if (df is None or df.empty) and retry > 0:
        time.sleep(0.3)  # 아주 짧게 쉬었다가
        df = inquire_price(
            env_dv="demo",
            fid_cond_mrkt_div_code="J",
            fid_input_iscd=symbol
        )

    if df is None or df.empty:
        raise ValueError(f"심볼 {symbol} 에 대한 시세 데이터를 찾을 수 없습니다.")

    row = df.iloc[0]  # 한 종목 = 한 줄

    # 3) 컬럼 이름이 존재하는지 체크하면서 값 추출
    def _get(field: str, default=None):
        return row[field] if field in df.columns else default

    # 숫자 변환 helper
    def _to_float(val):
        try:
            if val is None:
                return None
            return float(str(val).replace(",", ""))
        except Exception:
            return None

    def _to_int(val):
        try:
            if val is None:
                return None
            return int(str(val).replace(",", ""))
        except Exception:
            return None

    data: Dict[str, Any] = {
        "symbol": _get("stck_shrn_iscd", symbol),           # 종목코드
        "name": CODE_NAME_MAP.get(symbol, symbol),                 # 종목명 (컬럼명은 환경에 따라 다를 수 있음)

        # 시세 관련
        "price": _to_float(_get("stck_prpr")),              # 현재가
        "open": _to_float(_get("stck_oprc")),               # 시가
        "high": _to_float(_get("stck_hgpr")),               # 고가
        "low": _to_float(_get("stck_lwpr")),                # 저가

        "change": _to_float(_get("prdy_vrss")),             # 전일 대비 가격
        "change_rate": _to_float(_get("prdy_ctrt")),        # 전일 대비 등락률(%)

        # 거래 관련
        "volume": _to_int(_get("acml_vol")),                # 거래량
        "amount": _to_float(_get("acml_tr_pbmn")),          # 거래대금

        # 부가정보
        "market": _get("rprs_mrkt_kor_name", None),         # 시장 (예: KOSPI200)
        "sector": _get("bstp_kor_isnm", None),              # 업종 (예: 전기·전자)
        "per": _to_float(_get("per")),                      # PER
        "pbr": _to_float(_get("pbr")),                      # PBR
        "eps": _to_float(_get("eps")),
        "bps": _to_float(_get("bps")),
        "frgn_rate": _to_float(_get("hts_frgn_ehrt")),      # 외국인 지분율
    }

    return data


# --- 이 모듈을 단독 실행했을 때 간단 테스트 ---

if __name__ == "__main__":
    quote = get_domestic_quote("005930")
    print("=== get_domestic_quote('005930') 결과 ===")
    for k, v in quote.items():
        print(f"{k:12}: {v}")