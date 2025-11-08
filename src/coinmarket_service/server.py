import os

from dotenv import load_dotenv          # .env 파일에서 키=값 형식으로 정의된 환경변수를 읽어와서,
                                        # 현재 프로세스의 환경 변수(os.environ)에 주입해주는 라이브러리.
                                        # 로컬 개발 시 민감 정보(API 키 등)를 코드에 하드코딩하지 않고 관리하기 위함.
from typing import Any
import requests                         # HTTP 요청(REST API 호출)을 위해 사용하는 동기(블로킹) HTTP 클라이언트 라이브러리.
import json
from mcp.server.models import InitializationOptions  # MCP 서버 초기화 시 서버 이름, 버전, capabilities 등을 넘기기 위한 설정 객체.
import mcp.types as types               # MCP 프로토콜에서 사용하는 표준 타입 정의 (Tool, Resource, TextContent 등).
from mcp.server import NotificationOptions, Server   # Server: MCP 서버 본체 클래스. NotificationOptions: 알림 관련 옵션.
from pydantic import AnyUrl             # URL 형식을 검증/표현하는 타입. scheme, host, path 등을 구조적으로 다룸.
import mcp.server.stdio                # MCP 서버를 stdin/stdout 기반 스트림 위에서 실행하기 위한 유틸.


# 1. 환경 변수 로드 단계
# ----------------------------------------------------------------------
# load_dotenv()를 호출하면, 현재 디렉토리(또는 상위 디렉토리)에 있는 .env 파일을 읽어,
# 그 안의 KEY=VALUE 값을 os.environ에 추가해 준다.
# 이 프로젝트에서는 CoinMarketCap API 키를 .env에서 읽어 쓰기 위해 사용.
load_dotenv()

# os.getenv는 환경 변수에서 주어진 키 이름에 해당하는 값을 읽어온다.
# 여기서는 COINMARKET_API_KEY 라는 이름을 기대하고 있다.
API_KEY = os.getenv("COINMARKET_API_KEY")

# API 키가 설정되지 않은 경우, 서버를 실행해봤자 외부 API를 호출할 수 없으므로
# 여기서 즉시 에러를 발생시켜 개발자에게 설정 누락을 알린다.
# 주의: 메시지에는 COINMARKETCAP_API_KEY라고 써 있는데, 실제로 읽는 키 이름은 COINMARKET_API_KEY라서 혼동 가능.
# 실제 사용할 때는 키 이름과 에러 메시지를 반드시 통일해야 한다.
if not API_KEY:
    raise ValueError("Missing COINMARKETCAP_API_KEY environment variable")


# 2. 외부 API 헬퍼 함수들 (Data Layer)
# ----------------------------------------------------------------------
# 이 함수들은 MCP, 비즈니스 로직과 분리된 "순수한 HTTP 호출 래퍼" 역할을 한다.
# - 입력: 쿼리 조건(slug, symbol 등)
# - 출력: CoinMarketCap API의 JSON 응답(dict 형태)
# 상태를 저장하지 않고, 부를 때마다 외부 API에 요청을 던지는 구조.


# 최신 코인 리스트를 가져오는 비동기 함수.
# async로 선언되어 있지만, 내부에서 사용하는 requests는 동기 라이브러리라서
# 엄밀히 말하면 이벤트 루프를 블로킹한다. (데모/간단 구현 기준에서는 허용)
async def get_currency_listings() -> dict[str, Any]:
    # CoinMarketCap의 'cryptocurrency/listings/latest' 엔드포인트 URL.
    # 상위 코인들의 최신 시세/정보를 조회할 때 사용하는 공식 REST API.
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    
    # 요청 시 함께 전달할 쿼리 파라미터들.
    # - start: 조회 시작 순위 (1위부터 시작)
    # - limit: 몇 개의 코인을 가져올지 (여기서는 5개로 제한)
    # - convert: 가격 단위를 어떤 화폐 기준으로 변환할지 (USD 기준)
    parameters = {
      'start': '1',
      'limit': '5',
      'convert': 'USD'
    }

    # HTTP 요청 헤더 설정.
    # - Accepts: 응답을 JSON으로 받겠다는 의사 표현
    # - X-CMC_PRO_API_KEY: CoinMarketCap에서 발급받은 API 키 (인증용)
    headers = {
      'Accepts': 'application/json',
      'X-CMC_PRO_API_KEY': API_KEY,
    }

    # 실제 HTTP GET 요청 전송.
    # 이 호출은 네트워크 I/O 완료까지 현재 스레드를 블로킹한다.
    response = requests.get(url, headers=headers, params=parameters)

    # 응답 코드가 200대(성공)가 아닌 경우, HTTPError 예외를 발생시켜 상위에서 처리할 수 있게 한다.
    response.raise_for_status()

    # response.text는 JSON 문자열이므로, json.loads로 dict로 파싱.
    # 참고로 requests에는 response.json()도 있지만, 여기서는 수동 파싱을 사용.
    data = json.loads(response.text)

    # 최종적으로 파싱된 파이썬 dict를 반환.
    return data


# 특정 코인에 대한 실시간 시세(quote)를 가져오는 함수.
# slug(코인 식별용 문자열) 또는 symbol(예: BTC, ETH) 중 하나 또는 둘 다를 조건으로 사용할 수 있다.
async def get_quotes(slug: str | None, symbol: str | None) -> dict[str, Any]:
    # CoinMarketCap 'quotes/latest' 엔드포인트:
    # 특정 코인들의 현재 시세, 시가총액, 변동률 등을 조회하는 API.
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    
    # 공통 쿼리 파라미터: USD 기준 변환.
    parameters = {
      'convert': 'USD'
    }

    # slug가 주어졌다면, 해당 값을 쿼리 파라미터에 추가.
    # 예: slug='bitcoin'
    if slug:
        parameters['slug'] = slug

    # symbol이 주어졌다면, 해당 값을 쿼리 파라미터에 추가.
    # 예: symbol='BTC'
    if symbol:
        parameters['symbol'] = symbol

    # 인증/응답 형식을 위해 앞과 동일하게 헤더 설정.
    headers = {
      'Accepts': 'application/json',
      'X-CMC_PRO_API_KEY': API_KEY,
    }

    # GET 요청 전송 및 에러 검사.
    response = requests.get(url, headers=headers, params=parameters)
    response.raise_for_status()

    # JSON 응답을 dict로 변환.
    data = json.loads(response.text)
    return data


# 3. MCP Server 인스턴스 생성
# ----------------------------------------------------------------------
# MCP Server는 "이 프로세스가 MCP 프로토콜을 통해 어떤 기능(Tools, Resources)을 제공한다"를 표현하는 객체.
# 여기서 설정한 "coinmarket_service"는 클라이언트 설정에서 이 서버를 식별하는 이름으로 사용된다.
server = Server("coinmarket_service")


# 4. Resource listing 핸들러
# ----------------------------------------------------------------------
# MCP 프로토콜의 list_resources 요청에 응답하는 핸들러.
# "이 서버가 이런 URI 리소스들을 제공하고 있다"는 메타데이터를 반환한다.
@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    사용 가능한 coinmarket 리소스 목록을 MCP 클라이언트에게 알려준다.
    클라이언트는 이 정보를 바탕으로 read_resource를 호출해
    정적인(or 정적처럼 보이는) 데이터를 가져올 수 있다.
    """
    return [
        types.Resource(
            # uri: 리소스를 고유하게 식별하는 주소.
            # 관례적으로 custom scheme를 사용해 'coinmarket://' 형태로 정의.
            # AnyUrl은 scheme://host/path 구조를 기대하므로,
            # 실제 코드에서는 형식 유효성(예: host 유무)을 검토할 필요가 있다.
            uri=AnyUrl("coinmarket://cryptocurrency/listings"),
            name="Latest cryptocurrency listings from coinmarket",  # 사람 읽기용 이름
            description="Cryptocurrency listings",                  # 짧은 설명
            mimeType="application/json",                            # read_resource 응답 형식 힌트
        ),
        types.Resource(
            uri=AnyUrl("coinmarket://cryptocurrency/quotes"),
            name="Cryptocurrency quotes",
            description="Cryptocurrency quotes",
            mimeType="application/json",
        )
    ]


# 5. Resource read 핸들러
# ----------------------------------------------------------------------
# MCP의 read_resource 요청이 들어왔을 때, 해당 URI에 맞는 데이터를 돌려주는 역할.
@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    # uri.scheme: coinmarket://... 에서 'coinmarket' 부분.
    # 우리가 정의한 custom scheme는 coinmarket 뿐이므로, 다른 건 거부.
    if uri.scheme != "coinmarket":
        raise ValueError(f"Unsupported scheme: {uri.scheme}")

    # uri.path 기준으로 어떤 리소스를 요청했는지 판단.
    # match-case 문을 사용하여 각 path에 대해 분기 처리.
    match uri.path:
        case "/listings":
            try:
                # 최신 코인 리스트 데이터를 외부 API에서 가져온 뒤
                data = await get_currency_listings()
                # JSON 문자열로 예쁘게(indent=2) 포맷해서 반환.
                # read_resource는 문자열을 기대하므로, dict를 다시 문자열로 직렬화.
                return json.dumps(data, indent=2)
            except Exception as e:
                # 외부 API 에러, 네트워크 장애 등 모든 예외를 RuntimeError로 감싸서 전달.
                # 클라이언트 입장에서는 "리소스 읽기 실패"로 해석 가능.
                raise RuntimeError(f"Failed to fetch listings data: {e}")

        case "/quotes":
            try:
                # 이 부분은 개념상:
                # URI에 붙은 쿼리스트링(?slug=bitcoin&symbol=BTC)을 파싱해서
                # slug, symbol 값을 추출하려는 의도이다.
                #
                # 다만 AnyUrl에는 기본적으로 query_params() 메서드가 없으므로,
                # 실제 구현 시에는 uri.query를 직접 파싱해야 한다.
                # 예: from urllib.parse import parse_qsl; dict(parse_qsl(uri.query))
                query_params = {qp[0]: qp[1] for qp in uri.query_params()}
                slug = query_params.get("slug")
                symbol = query_params.get("symbol")

                # 추출한 slug/symbol을 기반으로 quotes 데이터 요청.
                data = await get_quotes(slug=slug, symbol=symbol)

                # 마찬가지로 JSON 문자열로 직렬화해서 반환.
                return json.dumps(data, indent=2)
            except Exception as e:
                raise RuntimeError(f"Failed to fetch quotes data: {e}")

        case _:
            # 위에서 정의하지 않은 path가 들어온 경우.
            # 예: coinmarket://foo/bar 같은 경우 "지원하지 않는 리소스"로 처리.
            raise ValueError(f"Unsupported path: {uri.path}")


# 6. Tool 목록 제공 핸들러
# ----------------------------------------------------------------------
# MCP의 list_tools 요청에 응답.
# "이 서버가 어떤 이름의 Tool을 제공하고, 각 Tool은 어떤 인자를 받는지"를 JSON Schema로 설명한다.
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    MCP 클라이언트에게 호출 가능한 tool 목록을 제공한다.
    각 tool의 inputSchema는 클라이언트가 적절한 인자를 구성하는 데 사용된다.
    """
    return [
        types.Tool(
            name="get_currency_listings",               # MCP에서 호출할 때 사용할 도구 이름
            description="Get latest cryptocurrency listings",  # 자연어 설명
            inputSchema={                               # 이 Tool이 받는 입력값의 JSON Schema
                "type": "object",
                "properties": {},                       # 인자 없음
                "required": [],
            },
        ),
        types.Tool(
            name="get_quotes",
            description="Get cryptocurrency quotes",
            inputSchema={
                "type": "object",
                "properties": {
                    # slug와 symbol 둘 다 선택적으로 받을 수 있도록 정의.
                    # 클라이언트는 이 schema를 보고 유효한 호출 형태를 구성할 수 있다.
                    "slug": {"type": "string"},
                    "symbol": {"type": "string"},
                },
                "required": [],  # 필수 인자 없음. (하지만 실제 운영 시 하나는 요구하는 게 안전하다.)
            },
        ),
    ]


# 7. Tool 호출 처리 핸들러
# ----------------------------------------------------------------------
# MCP의 call_tool 요청이 들어왔을 때 실제로 어떤 동작을 수행할지 정의하는 부분.
@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    MCP 클라이언트가 특정 tool(name)을 실행해 달라고 요청했을 때,
    이 함수를 통해 해당 tool을 식별하고, 적절한 로직을 수행한 뒤,
    결과를 MCP 표준 콘텐츠 타입(List[TextContent 등])으로 반환한다.
    """

    match name:
        # Tool 이름이 "get_currency_listings"인 경우:
        case "get_currency_listings":
            try:
                # 위에서 정의한 헬퍼 함수를 호출해 실제 데이터를 가져온다.
                data = await get_currency_listings()
                # MCP의 TextContent 타입으로 감싸서 반환.
                # type="text"는 "이건 텍스트 데이터다"라는 의미이며,
                # text에는 사람이 보거나 클라이언트가 파싱할 수 있는 JSON 문자열이 들어간다.
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(data, indent=2),
                    )
                ]
            except Exception as e:
                # 에러 발생 시, RuntimeError로 래핑하여 MCP 쪽에 전달.
                raise RuntimeError(f"Failed to fetch data: {e}")

        # Tool 이름이 "get_quotes"인 경우:
        case "get_quotes":
            # arguments는 MCP 클라이언트가 call_tool 시 보낸 JSON 인자.
            # 없을 수도 있으므로 None 체크.
            if not arguments:
                slug = None
                symbol = None
            else:
                # dict.get을 사용해 slug, symbol을 안전하게 추출.
                slug = arguments.get("slug")
                symbol = arguments.get("symbol")

            try:
                # 헬퍼 함수 호출로 실제 quote 데이터 조회.
                data = await get_quotes(slug=slug, symbol=symbol)
                # 마찬가지로 TextContent로 래핑해서 반환.
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(data, indent=2),
                    )
                ]
            except Exception as e:
                raise RuntimeError(f"Failed to fetch data: {e}")

        # 정의되지 않은 tool 이름에 대한 방어 코드.
        # 클라이언트가 잘못된 이름을 호출했음을 명확히 알리기 위해 ValueError 발생.
        case _:
            raise ValueError(f"Unsupported tool: {name}")


# 8. MCP 서버 엔트리포인트(main)
# ----------------------------------------------------------------------
# 이 함수는 실제로 MCP 서버를 "표준입출력 기반 프로세스"로 실행하는 진입점이다.
# MCP 클라이언트(예: Claude Desktop)는 설정 파일에 이 main을 실행하는 커맨드를 적어두고,
# 필요할 때마다 이 프로세스를 띄워서 Tool 호출을 주고받는다.
async def main():
    # stdio_server() 컨텍스트 매니저는 (read_stream, write_stream)를 제공한다.
    # - read_stream: 클라이언트 → 서버 방향(MCP 요청) 입력 스트림
    # - write_stream: 서버 → 클라이언트 방향(MCP 응답) 출력 스트림
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # server.run은:
        # - 위에서 등록한 list_tools, call_tool, list_resources, read_resource 핸들러를 사용해서
        # - 들어오는 MCP 메시지를 처리하고,
        # - 응답을 write_stream으로 돌려보내는 이벤트 루프를 수행한다.
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="coinmarket_service",   # MCP 클라이언트에게 보고되는 서버 이름
                server_version="0.1.0",             # 서버 버전 (로깅/호환성 용)
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),  # 알림 관련 설정 (여기서는 기본값)
                    experimental_capabilities={},               # 실험적 기능 (없으면 빈 dict)
                ),
            ),
        )

