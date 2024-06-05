from typing import Any

from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.wos.tools.wos_search import WOSSearchTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class WOSProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            WOSSearchTool().fork_tool_runtime(
                meta={
                    "credentials": credentials,
                }
            ).invoke(
                user_id='',
                tool_parameters={
                    "query": "test",
                    "query_type": "TS",
                    "db": "WOS",
                    "limit": 10,
                    "page": 1
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
