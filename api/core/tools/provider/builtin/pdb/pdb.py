from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.pdb.tools.pdb_citation import PDBCitationsTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class PDBProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            PDBCitationsTool().fork_tool_runtime(
                runtime={
                    "credentials": credentials,
                }
            ).invoke(
                user_id='',
                tool_parameters={
                    "ids": ['10.1002/pi.5188', '10.1007/s00894-022-05373-8', ],
                    "fields": "title,abstract,authors"
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))