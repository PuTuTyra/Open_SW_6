import asyncio
import copy
import json
import logging
import os
import time
from base64 import b64decode
from collections import namedtuple
from collections.abc import Callable
from datetime import datetime
from io import StringIO
import pandas as pd
import requests
import websockets
import yaml
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
#현재 운영체제에 맞는 콘솔 화면 지우기 명령어 실행
clearConsole = lambda: os.system("cls" if os.name in ("nt", "dos") else "clear")

key_bytes = 32
#KIS/config 위치 설정
config_root = os.path.join(os.path.expanduser("~"), "KIS", "config")
#날짜별로 고유한 폴더를 구성해 오늘 날짜 기준 데이터를 저장하거나 관리하기 위한 폴더 경로를 생성
token_tmp = os.path.join(
    config_root, f"KIS{datetime.today().strftime("%Y%m%d")}"
) 
# 접근토큰 관리하는 파일 존재여부 체크, 없으면 생성
if os.path.exists(token_tmp) == False:
    f = open(token_tmp, "w+")
#API 설정을 담은 구성 파일을 읽고 _cfg 변수에 저장
with open(os.path.join(config_root, "kis_devlp.yaml"), encoding="UTF-8") as f:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)

_TRENV = tuple()
_last_auth_time = datetime.now()
_autoReAuth = False
_DEBUG = False
_isPaper = False
_smartSleep = 0.1
# 기본 헤더값 정의
_base_headers = {
    "Content-Type": "application/json",
    "Accept": "text/plain",
    "charset": "UTF-8",
    "User-Agent": _cfg["my_agent"],
}
# 토큰 발급 받아 저장 (토큰값, 토큰 유효시간,1일, 6시간 이내 발급신청시는 기존 토큰값과 동일, 발급시 알림톡 발송)
def save_token(my_token, my_expired):
    #만료 시간을 저장
    valid_date = datetime.strptime(my_expired, "%Y-%m-%d %H:%M:%S")
    #토큰과 만료 날짜 정보를 읽기 쉬운 형식으로 파일에 기록
    with open(token_tmp, "w", encoding="utf-8") as f:
        f.write(f"token: {my_token}\n")
        f.write(f"valid-date: {valid_date}\n")

# 토큰 확인 (토큰값, 토큰 유효시간_1일, 6시간 이내 발급신청시는 기존 토큰값과 동일, 발급시 알림톡 발송)
def read_token():
    try:
        # 토큰이 저장된 파일 읽기
        with open(token_tmp, encoding="UTF-8") as f:
            tkg_tmp = yaml.load(f, Loader=yaml.FullLoader)
        # 토큰 만료 일,시간
        exp_dt = datetime.strftime(tkg_tmp["valid-date"], "%Y-%m-%d %H:%M:%S")
        # 현재일자,시간
        now_dt = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        # 저장된 토큰 만료일자 체크 (만료일시 > 현재일시 인경우 보관 토큰 리턴)
        if exp_dt > now_dt:
            return tkg_tmp["token"]
        else:
            return None
    except Exception:
        return None
# 토큰 유효시간 체크해서 만료된 토큰이면 재발급처리
def _getBaseHeader():
    if _autoReAuth:
        reAuth()
    return copy.deepcopy(_base_headers)
# 가져오기 : 앱키, 앱시크리트, 종합계좌번호(계좌번호 중 숫자8자리), 계좌상품코드(계좌번호 중 숫자2자리), 토큰, 도메인
def _setTRENV(cfg):
    nt1 = namedtuple(
        "KISEnv",
        ["my_app", "my_sec", "my_acct", "my_prod", "my_htsid", "my_token", "my_url", "my_url_ws"],
    )
    d = {
        "my_app": cfg["my_app"],  # 앱키
        "my_sec": cfg["my_sec"],  # 앱시크리트
        "my_acct": cfg["my_acct"],  # 종합계좌번호(8자리)
        "my_prod": cfg["my_prod"],  # 계좌상품코드(2자리)
        "my_htsid": cfg["my_htsid"],  # HTS ID
        "my_token": cfg["my_token"],  # 토큰
        "my_url": cfg[
            "my_url"
        ],  # 실전 도메인 (https://openapi.koreainvestment.com:9443)
        "my_url_ws": cfg["my_url_ws"],
    }  # 모의 도메인 (https://openapivts.koreainvestment.com:29443)

    global _TRENV
    _TRENV = nt1(**d)
#모의투자 여부 반환
def isPaperTrading():  
    return _isPaper
# 실전투자면 'prod', 모의투자면 'vps'
def changeTREnv(token_key, svr="prod", product=_cfg["my_prod"]):
    cfg = dict()
    #모의 투자 여부
    global _isPaper
    if svr == "prod":  # 실전투자
        ak1 = "my_app"  # 실전투자용 앱키
        ak2 = "my_sec"  # 실전투자용 앱시크리트
        _isPaper = False
        _smartSleep = 0.05
    elif svr == "vps":  # 모의투자
        ak1 = "paper_app"  # 모의투자용 앱키
        ak2 = "paper_sec"  # 모의투자용 앱시크리트
        _isPaper = True
        _smartSleep = 0.5
    #투자 상품에 따른 정보 불러오기
    cfg["my_app"] = _cfg[ak1]
    cfg["my_sec"] = _cfg[ak2]
    if svr == "prod" and product == "01":  # 실전투자 주식투자, 위탁계좌, 투자계좌
        cfg["my_acct"] = _cfg["my_acct_stock"]
    elif svr == "prod" and product == "03":  # 실전투자 선물옵션(파생)
        cfg["my_acct"] = _cfg["my_acct_future"]
    elif svr == "prod" and product == "08":  # 실전투자 해외선물옵션(파생)
        cfg["my_acct"] = _cfg["my_acct_future"]
    elif svr == "prod" and product == "22":  # 실전투자 개인연금저축계좌
        cfg["my_acct"] = _cfg["my_acct_stock"]
    elif svr == "prod" and product == "29":  # 실전투자 퇴직연금계좌
        cfg["my_acct"] = _cfg["my_acct_stock"]
    elif svr == "vps" and product == "01":  # 모의투자 주식투자, 위탁계좌, 투자계좌
        cfg["my_acct"] = _cfg["my_paper_stock"]
    elif svr == "vps" and product == "03":  # 모의투자 선물옵션(파생)
        cfg["my_acct"] = _cfg["my_paper_future"]
    cfg["my_prod"] = product
    cfg["my_htsid"] = _cfg["my_htsid"]
    cfg["my_url"] = _cfg[svr]
    #기존 토큰 불러오기
    try:
        my_token = _TRENV.my_token
    except AttributeError:
        my_token = ""
    cfg["my_token"] = my_token if token_key else token_key
    cfg["my_url_ws"] = _cfg["ops" if svr == "prod" else "vops"]
    #최종 환경 변수 설정
    _setTRENV(cfg)
#JSON 데이터를 객체로 변환
def _getResultObject(json_data):
    _tc_ = namedtuple("res", json_data.keys())

    return _tc_(**json_data)

def auth(svr="prod", product=_cfg["my_prod"], url=None):
    p = {
        "grant_type": "client_credentials",
    }
    #svr인자 값에 따라 실전투자와 모의투자를 구분. 이후 환경에 맞는 앱키와 앱시크리트 설정 
    if svr == "prod":  # 실전투자
        ak1 = "my_app"  # 앱키 (실전투자용)
        ak2 = "my_sec"  # 앱시크리트 (실전투자용)
    elif svr == "vps":  # 모의투자
        ak1 = "paper_app"  # 앱키 (모의투자용)
        ak2 = "paper_sec"  # 앱시크리트 (모의투자용)
    # 앱키, 앱시크리트 가져오기
    p["appkey"] = _cfg[ak1]
    p["appsecret"] = _cfg[ak2]
    # 기존 발급된 토큰이 있는지 확인
    saved_token = read_token()  # 기존 발급 토큰 확인
    # 기존 발급 토큰 확인이 안되면 발급처리
    if saved_token is None: 
        #새 토큰값이 필요할 때 요청 보내기
        url = f"{_cfg[svr]}/oauth2/tokenP"
        res = requests.post(
            #요청 데이터는 JSON 형식
            url, data=json.dumps(p), headers=_getBaseHeader()
        )  
        rescode = res.status_code
        #정상 발급인 경우
        if rescode == 200: 
            #access_token과 만료시간 추출
            my_token = _getResultObject(res.json()).access_token  
            my_expired = _getResultObject(
                res.json()
            ).access_token_token_expired
            #토큰과 만료정보를 저장  
            save_token(my_token, my_expired)  
        else:
            print("Get Authentification token fail!\nYou have to restart your app!!!")
            return
    else:
        my_token = saved_token  # 기존 발급 토큰 확인되어 기존 토큰 사용

    #환경별 설정 마무리
    changeTREnv(my_token, svr, product)
    #실제 API인증에 필요한 헤더값 할당
    _base_headers["authorization"] = f"Bearer {my_token}"
    _base_headers["appkey"] = _TRENV.my_app
    _base_headers["appsecret"] = _TRENV.my_sec
    #인증 토큰을 받은 최신 시간을 관리
    global _last_auth_time
    _last_auth_time = datetime.now()
    #디버그 모드일 경우 인증 완료 로그 출력
    if _DEBUG:
        print(f"[{_last_auth_time}] => get AUTH Key completed!")
#1일 경과시 토큰 재발급 시도
def reAuth(svr="prod", product=_cfg["my_prod"]):
    n2 = datetime.now()
    if (n2 - _last_auth_time).seconds >= 86400: 
        auth(svr, product)
#설정값 반환
def getEnv():
    return _cfg
#과도한 요청 방지장치
def smart_sleep():
    if _DEBUG:
        print(f"[RateLimit] Sleeping {_smartSleep}s ")

    time.sleep(_smartSleep)
#현재 프로그램이 사용하는 투자 환경 설정 정보 반환
def getTREnv():
    return _TRENV
# 주문/정정/취소 요청 시, 데이터 변조를 방지하기 위해 서버가 제공하는 해시 키를 받아 요청 헤더에 반드시 포함시켜야 함
def set_order_hash_key(h, p):
    #현재 환경설정에서 해시 키 발급 API URL 생성
    url = f"{getTREnv().my_url}/uapi/hashkey"  # hashkey 발급 API URL
    #주문 파라미터를 JSON으로 변환해 POST 요청, 기존 헤더 h와 함께 API 서버로 전송
    res = requests.post(url, data=json.dumps(p), headers=h)
    rescode = res.status_code
    if rescode == 200:
        #응답에서 해시 키(HASH)를 추출해 헤더 h의 "hashkey" 항목에 저장
        h["hashkey"] = _getResultObject(res.json()).HASH
    #실패 시 에러 코드 출력
    else:
        print("Error:", rescode)
# API 호출 응답에 필요한 처리 공통 함수
class APIResp:
    def __init__(self, resp):
        self._rescode = resp.status_code
        self._resp = resp
        self._header = self._setHeader()
        self._body = self._setBody()
        self._err_code = self._body.msg_cd
        self._err_message = self._body.msg1
    #HTTP 응답코드 반환
    def getResCode(self):
        return self._rescode
    #응답의 헤더 파싱 후 객체로 변환
    def _setHeader(self):
        fld = dict()
        for x in self._resp.headers.keys():
            if x.islower():
                fld[x] = self._resp.headers.get(x)
        _th_ = namedtuple("header", fld.keys())

        return _th_(**fld)
    #응답의 본문 파싱 후 객체로 변환
    def _setBody(self):
        _tb_ = namedtuple("body", self._resp.json().keys())

        return _tb_(**self._resp.json())
    #헤더 응답 객체 접근
    def getHeader(self):
        return self._header
    #본문 응답 객체 접근
    def getBody(self):
        return self._body
    #전체 응답 객체 접근
    def getResponse(self):
        return self._resp
    #성공 여부 반환
    def isOK(self):
        try:
            if self.getBody().rt_cd == "0":
                return True
            else:
                return False
        except:
            return False

    def getErrorCode(self):
        return self._err_code

    def getErrorMessage(self):
        return self._err_message
    #헤더와 본문 모든 필드와 값을 보기 좋게 출력
    def printAll(self):
        print("<Header>")
        for x in self.getHeader()._fields:
            print(f"\t-{x}: {getattr(self.getHeader(), x)}")
        print("<Body>")
        for x in self.getBody()._fields:
            print(f"\t-{x}: {getattr(self.getBody(), x)}")
    #에러 발생 시 URL, 코드, 메시지 등 상세 결과를 콘솔에 출력
    def printError(self, url):
        print(
            "-------------------------------\nError in response: ",
            self.getResCode(),
            " url=",
            url,
        )
        print(
            "rt_cd : ",
            self.getBody().rt_cd,
            "/ msg_cd : ",
            self.getErrorCode(),
            "/ msg1 : ",
            self.getErrorMessage(),
        )
        print("-------------------------------")
    #클래스 끝

class APIRespError(APIResp):
    def __init__(self, status_code, error_text):
        self.status_code = status_code
        self.error_text = error_text
        self._error_code = str(status_code)
        self._error_message = error_text

    def isOK(self):
        return False
    #에러 코드 제공
    def getErrorCode(self):
        return self._error_code
    #에러 메시지 제공
    def getErrorMessage(self):
        return self._error_message
    # 본문과 헤더 접근 시 빈 상태 객체를 반환하여 AttributeError 방지 및 프로그램 안정성 유지
    def getBody(self):
        class EmptyBody:
            def __getattr__(self, name):
                return None

        return EmptyBody()

    def getHeader(self):
        class EmptyHeader:
            tr_cont = ""

            def __getattr__(self, name):
                return ""

        return EmptyHeader()
    #에러 정보를 보기 쉽게 출력
    def printAll(self):
        print(f"=== ERROR RESPONSE ===")
        print(f"Status Code: {self.status_code}")
        print(f"Error Message: {self.error_text}")
        print(f"======================")

    def printError(self, url=""):
        print(f"Error Code : {self.status_code} | {self.error_text}")
        if url:
            #URL 정보가 있으면 함께 출력
            print(f"URL: {url}")
#한국투자증권 오픈API를 호출하는 기능을 총괄하는 함수
def _url_fetch(
        api_url, ptr_id, tr_cont, params, appendHeaders=None, postFlag=False, hashFlag=True
):
    #API 기본 URL을 가져와 요청할 api_url과 합쳐 전체 요청 URL 생성
    url = f"{getTREnv().my_url}{api_url}"
    # 기본 header 구성
    headers = _getBaseHeader()  
    # 트랜잭션 ID를 환경에 맞게 조정해 헤더에 삽입
    tr_id = ptr_id
    if ptr_id[0] in ("T", "J", "C"):  
        if isPaperTrading():  
            tr_id = "V" + ptr_id[1:]
    #고객 타입과 트랜잭션 내용도 헤더에 설정
    headers["tr_id"] = tr_id  
    headers["custtype"] = "P"  
    headers["tr_cont"] = tr_cont  
    #추가 헤더를 받아 헤더에 반영
    if appendHeaders is not None:
        if len(appendHeaders) > 0:
            for x in appendHeaders.keys():
                headers[x] = appendHeaders.get(x)
    #요청 URL, 트랜잭션 ID, 헤더, 파라미터 내용을 로그로 출력
    if _DEBUG:
        print("< Sending Info >")
        print(f"URL: {url}, TR: {tr_id}")
        print(f"<header>\n{headers}")
        print(f"<body>\n{params}")
    #postFlag가 True면 POST 요청(requests.post), 아니면 GET 요청(requests.get) 수행
    if postFlag:
        #POST 시 파라미터를 JSON 문자열로 전송
        res = requests.post(url, headers=headers, data=json.dumps(params))
    else:
        res = requests.get(url, headers=headers, params=params)

    if res.status_code == 200:
        #APIResp 객체로 감싸서 반환
        ar = APIResp(res)
        if _DEBUG:
            ar.printAll()
        return ar
    else:
        # 에러 메시지를 출력하고 APIRespError 객체를 반환
        print("Error Code : " + str(res.status_code) + " | " + res.text)
        return APIRespError(res.status_code, res.text)

#웹소켓 API 호출 시 기본으로 사용하는 헤더 세트
_base_headers_ws = {
    "content-type": "utf-8",
}
# 웹소켓 통신을 위한 기본 헤더를 반환
def _getBaseHeader_ws():
    if _autoReAuth:
        #토큰 갱신 등 자동 재인증 처리 수행
        reAuth_ws()
    #_base_headers_ws에서 정의된 웹소켓 기본 헤더를 깊은 복사하여 반환
    return copy.deepcopy(_base_headers_ws)
#웹소켓 API용 인증 토큰(approval key)를 발급, 웹소켓 통신에 필요한 환경 설정과 인증 정보를 초기화
def auth_ws(svr="prod", product=_cfg["my_prod"]):
    p = {"grant_type": "client_credentials"}
    #svr 값에 따라 환경 설정
    if svr == "prod":#실전투자
        ak1 = "my_app"
        ak2 = "my_sec"
    elif svr == "vps":#모의투자
        ak1 = "paper_app"
        ak2 = "paper_sec"

    p["appkey"] = _cfg[ak1]
    p["secretkey"] = _cfg[ak2]

    url = f"{_cfg[svr]}/oauth2/Approval"
    res = requests.post(url, data=json.dumps(p), headers=_getBaseHeader())  # 토큰 발급
    rescode = res.status_code
    if rescode == 200:  # 토큰 정상 발급
        approval_key = _getResultObject(res.json()).approval_key
    else:
        #발급에 실패하면 경고 메시지 출력 후 종료
        print("Get Approval token fail!\nYou have to restart your app!!!")
        return
    #성공 시 환경 변수 초기화
    changeTREnv(None, svr, product)
    #발급받은 키값을 글로벌 웹소켓 헤더에 넣음
    _base_headers_ws["approval_key"] = approval_key
    #마지막 인증 시간 기록
    global _last_auth_time
    _last_auth_time = datetime.now()
    #디버그 모드면 인증 완료 로그 출력
    if _DEBUG:
        print(f"[{_last_auth_time}] => get AUTH Key completed!")
# 웹소켓용 인증 토큰 유효 시간 검사, 토큰 만료 기준 초과시 새 토큰을 재발급받는 웹소켓 전용 재인증 함수
def reAuth_ws(svr="prod", product=_cfg["my_prod"]):
    n2 = datetime.now()
    if (n2 - _last_auth_time).seconds >= 86400:
        auth_ws(svr, product)
#웹소켓 API 호출을 위해 전송할 요청 데이터와 헤더를 준비하는 함수
def data_fetch(tr_id, tr_type, params, appendHeaders=None) -> dict:
    #웹소켓 기본 헤더를 복사해 가져옴
    headers = _getBaseHeader_ws()  # 기본 header 값 정리
    #트랜잭션 타입과 고객 유형 설정
    headers["tr_type"] = tr_type
    headers["custtype"] = "P"
    #appendHeaders가 있으면 추가 헤더 항목들을 기본 헤더에 병합
    if appendHeaders is not None:
        if len(appendHeaders) > 0:
            for x in appendHeaders.keys():
                headers[x] = appendHeaders.get(x)
    #디버그 모드일 경우 전송할 트랜잭션 ID와 헤더 정보를 출력
    if _DEBUG:
        print("< Sending Info >")
        print(f"TR: {tr_id}")
        print(f"<header>\n{headers}")

    inp = {
        "tr_id": tr_id,
    }
    inp.update(params)
    #헤더 딕셔너리와 본문 딕셔너리를 포함하는 큰 딕셔너리를 반환
    return {"header": headers, "body": {"input": inp}}

# 한국투자증권 웹소켓 서버로부터 받은 JSON 형식의 메시지를 파싱하고,메시지 내용을 주요 상태와 함께 이름 있는 튜플 객체로 변환하여 반환
def system_resp(data):
    #초기 변수 설정
    isPingPong = False
    isUnSub = False
    isOk = False
    tr_msg = None
    tr_key = None
    encrypt, iv, ekey = None, None, None
    #문자열 data를 JSON 객체로 변환
    rdic = json.loads(data)
    #tr_id 추출
    tr_id = rdic["header"]["tr_id"]
    if tr_id != "PINGPONG":
        #tr_id가 "PINGPONG"이 아니면 tr_key, encrypt 값을 헤더에서 추출
        tr_key = rdic["header"]["tr_key"]
        encrypt = rdic["header"]["encrypt"]
    if rdic.get("body", None) is not None:
        #본문이 있으면 정상 응답 여부를 판단
        isOk = True if rdic["body"]["rt_cd"] == "0" else False
        tr_msg = rdic["body"]["msg1"]
        #응답 메시지 복호화에 필요한 iv와 key를 추출
        if "output" in rdic["body"]:
            iv = rdic["body"]["output"]["iv"]
            ekey = rdic["body"]["output"]["key"]
            #메시지가 "UNSUB"으로 시작하면 구독 해제(isUnSub) 상태로 판단
        isUnSub = True if tr_msg[:5] == "UNSUB" else False
    else:
        #본문이 없으면 isPingPong을 True로 설정
        isPingPong = True if tr_id == "PINGPONG" else False
    #응답 상태와 키, 메시지, 암호화 관련 값들을 포함하는 SysMsg namedtuple을 생성
    nt2 = namedtuple(
        "SysMsg",
        [
            "isOk",
            "tr_id",
            "tr_key",
            "isUnSub",
            "isPingPong",
            "tr_msg",
            "iv",
            "ekey",
            "encrypt",
        ],
    )
    d = {
        "isOk": isOk,
        "tr_id": tr_id,
        "tr_key": tr_key,
        "tr_msg": tr_msg,
        "isUnSub": isUnSub,
        "isPingPong": isPingPong,
        "iv": iv,
        "ekey": ekey,
        "encrypt": encrypt,
    }
    #이를 반환해 이후 코드에서 각 상태 값에 편리하게 접근 가능
    return nt2(**d)


def aes_cbc_base64_dec(key, iv, cipher_text):
    if key is None or iv is None:
        raise AttributeError("key and iv cannot be None")

    cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))


#####
open_map: dict = {}


def add_open_map(
        name: str,
        request: Callable[[str, str, ...], (dict, list[str])],
        data: str | list[str],
        kwargs: dict = None,
):
    if open_map.get(name, None) is None:
        open_map[name] = {
            "func": request,
            "items": [],
            "kwargs": kwargs,
        }

    if type(data) is list:
        open_map[name]["items"] += data
    elif type(data) is str:
        open_map[name]["items"].append(data)


data_map: dict = {}


def add_data_map(
        tr_id: str,
        columns: list = None,
        encrypt: str = None,
        key: str = None,
        iv: str = None,
):
    if data_map.get(tr_id, None) is None:
        data_map[tr_id] = {"columns": [], "encrypt": False, "key": None, "iv": None}

    if columns is not None:
        data_map[tr_id]["columns"] = columns

    if encrypt is not None:
        data_map[tr_id]["encrypt"] = encrypt

    if key is not None:
        data_map[tr_id]["key"] = key

    if iv is not None:
        data_map[tr_id]["iv"] = iv


class KISWebSocket:
    api_url: str = ""
    on_result: Callable[
        [websockets.ClientConnection, str, pd.DataFrame, dict], None
    ] = None
    result_all_data: bool = False

    retry_count: int = 0
    amx_retries: int = 0

    # init
    def __init__(self, api_url: str, max_retries: int = 3):
        self.api_url = api_url
        self.max_retries = max_retries

    # private
    async def __subscriber(self, ws: websockets.ClientConnection):
        async for raw in ws:
            logging.info("received message >> %s" % raw)
            show_result = False

            df = pd.DataFrame()

            if raw[0] in ["0", "1"]:
                d1 = raw.split("|")
                if len(d1) < 4:
                    raise ValueError("data not found...")

                tr_id = d1[1]

                dm = data_map[tr_id]
                d = d1[3]
                if dm.get("encrypt", None) == "Y":
                    d = aes_cbc_base64_dec(dm["key"], dm["iv"], d)

                df = pd.read_csv(
                    StringIO(d), header=None, sep="^", names=dm["columns"], dtype=object
                )

                show_result = True

            else:
                rsp = system_resp(raw)

                tr_id = rsp.tr_id
                add_data_map(
                    tr_id=rsp.tr_id, encrypt=rsp.encrypt, key=rsp.ekey, iv=rsp.iv
                )

                if rsp.isPingPong:
                    print(f"### RECV [PINGPONG] [{raw}]")
                    await ws.pong(raw)
                    print(f"### SEND [PINGPONG] [{raw}]")

                if self.result_all_data:
                    show_result = True

            if show_result is True and self.on_result is not None:
                self.on_result(ws, tr_id, df, data_map[tr_id])

    async def __runner(self):
        if len(open_map.keys()) > 40:
            raise ValueError("Subscription's max is 40")

        url = f"{getTREnv().my_url_ws}{self.api_url}"

        while self.retry_count < self.max_retries:
            try:
                async with websockets.connect(url) as ws:
                    # request subscribe
                    for name, obj in open_map.items():
                        await self.send_multiple(
                            ws, obj["func"], "1", obj["items"], obj["kwargs"]
                        )

                    # subscriber
                    await asyncio.gather(
                        self.__subscriber(ws),
                    )
            except Exception as e:
                print("Connection exception >> ", e)
                self.retry_count += 1
                await asyncio.sleep(1)

    # func
    @classmethod
    async def send(
            cls,
            ws: websockets.ClientConnection,
            request: Callable[[str, str, ...], (dict, list[str])],
            tr_type: str,
            data: str,
            kwargs: dict = None,
    ):
        k = {} if kwargs is None else kwargs
        msg, columns = request(tr_type, data, **k)

        add_data_map(tr_id=msg["body"]["input"]["tr_id"], columns=columns)

        logging.info("send message >> %s" % json.dumps(msg))

        await ws.send(json.dumps(msg))
        smart_sleep()

    async def send_multiple(
            self,
            ws: websockets.ClientConnection,
            request: Callable[[str, str, ...], (dict, list[str])],
            tr_type: str,
            data: list | str,
            kwargs: dict = None,
    ):
        if type(data) is str:
            await self.send(ws, request, tr_type, data, kwargs)
        elif type(data) is list:
            for d in data:
                await self.send(ws, request, tr_type, d, kwargs)
        else:
            raise ValueError("data must be str or list")

    @classmethod
    def subscribe(
            cls,
            request: Callable[[str, str, ...], (dict, list[str])],
            data: list | str,
            kwargs: dict = None,
    ):
        add_open_map(request.__name__, request, data, kwargs)

    def unsubscribe(
            self,
            ws: websockets.ClientConnection,
            request: Callable[[str, str, ...], (dict, list[str])],
            data: list | str,
    ):
        self.send_multiple(ws, request, "2", data)

    # start
    def start(
            self,
            on_result: Callable[
                [websockets.ClientConnection, str, pd.DataFrame, dict], None
            ],
            result_all_data: bool = False,
    ):
        self.on_result = on_result
        self.result_all_data = result_all_data
        try:
            asyncio.run(self.__runner())
        except KeyboardInterrupt:
            print("Closing by KeyboardInterrupt")