from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.uniprot.tools.uniprot_search import UniProtSearchTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class UniProtProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            UniProtSearchTool().fork_tool_runtime(
                runtime={
                    "credentials": credentials,
                }
            ).invoke(
                user_id='',
                tool_parameters={
                    "query": "accession:P05067",
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
        