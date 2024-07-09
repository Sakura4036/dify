from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.literature.tools.literature import LiteratureSearchTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class LiteratureProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            LiteratureSearchTool().fork_tool_runtime(
                runtime={
                    "credentials": credentials,
                }
            ).invoke(
                user_id='',
                tool_parameters={
                    "query": "proteinA",
                    "num_results": 10,
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
