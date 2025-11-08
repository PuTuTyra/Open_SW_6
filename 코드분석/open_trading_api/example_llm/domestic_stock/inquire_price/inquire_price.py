import sys
import logging

import pandas as pd
#현재 디렉토리나 현재 파일을 기준으로 2단계 상위 디렉토리까지 모듈 탐색 경로에 포함시켜, 이 경로들에 있는 모듈이나 
#패키지를 import 할 수 있도록 함. 프로젝트 구조상 상위 폴더/현재 폴더의 kis_auth 모듈을 쉽게 import하기 위함.
sys.path.extend(['../..', '.'])
import kis_auth as ka
# 기본 로깅 설정, 로그 출력 시 INFO 및 그 이상 레벨 메시지를 보여주도록 지정하는 구문. 상태 확인, 로그 과다 출력 방지.
logging.basicConfig(level=logging.INFO)
#######################################################
# [국내주식] 기본시세 > 주식현재가 시세[v1_국내주식-008]
#######################################################
# 상수 정의
API_URL = "/uapi/domestic-stock/v1/quotations/inquire-price"

def inquire_price(
    env_dv: str,  # [필수] 실전모의구분 (ex. real:실전, demo:모의)
    fid_cond_mrkt_div_code: str,  # [필수] 조건 시장 분류 코드 (ex. J:KRX, NX:NXT, UN:통합)
    fid_input_iscd: str  # [필수] 입력 종목코드 (ex. 종목코드 (ex 005930 삼성전자), ETN은 종목코드 6자리 앞에 Q 입력 필수)
) -> pd.DataFrame:
    """
    주식 현재가 시세 API입니다. 실시간 시세를 원하신다면 웹소켓 API를 활용하세요.

    ※ 종목코드 마스터파일 파이썬 정제코드는 한국투자증권 Github 참고 부탁드립니다.
    https://github.com/koreainvestment/open-trading-api/tree/main/stocks_info
    
    Args:
        env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
        fid_cond_mrkt_div_code (str): [필수] 조건 시장 분류 코드 (ex. J:KRX, NX:NXT, UN:통합)
        fid_input_iscd (str): [필수] 입력 종목코드 (ex. 종목코드 (ex 005930 삼성전자), ETN은 종목코드 6자리 앞에 Q 입력 필수)

    Returns:
        pd.DataFrame: 주식 현재가 시세 데이터
        
    Example:
        >>> df = inquire_price("real", "J", "005930")
        >>> print(df)
    """
    #실전 모의 여부 미입력시
    if env_dv == "" or env_dv is None:
        raise ValueError("env_dv is required (e.g. 'real:실전, demo:모의')")
    #시장 구분 코드 미입력시
    if fid_cond_mrkt_div_code == "" or fid_cond_mrkt_div_code is None:
        raise ValueError("fid_cond_mrkt_div_code is required (e.g. 'J:KRX, NX:NXT, UN:통합')")
    #종목코드 미입력시
    if fid_input_iscd == "" or fid_input_iscd is None:
        raise ValueError("fid_input_iscd is required (e.g. '종목코드 (ex 005930 삼성전자), ETN은 종목코드 6자리 앞에 Q 입력 필수')")
    #실전 모의 여부 입력 시 tr_id를 설정
    if env_dv == "real":
        tr_id = "FHKST01010100"
    elif env_dv == "demo":
        tr_id = "FHKST01010100"
    else:
        raise ValueError("env_dv can only be 'real' or 'demo'")

    params = {
        "FID_COND_MRKT_DIV_CODE": fid_cond_mrkt_div_code,
        "FID_INPUT_ISCD": fid_input_iscd
    }
    #국내 주식 현재가 시세 조회 API를 인증 정보를 포함해 실제 요청하고,결과 응답을 받아 res에 저장
    res = ka._url_fetch(API_URL, tr_id, "", params)
    #API 호출 성공 시 응답 데이터를 표 형태인 판다스 데이터프레임으로 변환해 반환
    #실패 시 에러 메시지 출력 후 빈 데이터프레임 반환으로 오류 상황 알림
    if res.isOK():
        current_data = pd.DataFrame(res.getBody().output, index=[0])
        return current_data
    else:
        res.printError(url=API_URL)
        return pd.DataFrame() 