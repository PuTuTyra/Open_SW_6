# mcp_client_utils.py

import sys
import json
from pathlib import Path
from typing import Any, Dict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).parent


async def call_mcp_tool_json(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP 서버를 stdio로 실행하고, 지정한 MCP 툴을 호출한 뒤
    content[0].text에 담긴 JSON을 파싱해서 dict로 반환합니다.
    - 매 요청마다 MCP 서버를 새로 띄우는 구조 (개발용/소규모 서비스에 적당)
    """

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_ROOT / "mcp_server.py")],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(tool_name, arguments)
            text = result.content[0].text
            return json.loads(text)