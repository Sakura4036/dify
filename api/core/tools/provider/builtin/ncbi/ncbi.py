from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.ncbi.tools.ncbi_blast import NCBIBlASTTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class NCBIProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            NCBIBlASTTool().fork_tool_runtime(
                runtime={
                    "credentials": credentials,
                }
            ).invoke(
                user_id='',
                tool_parameters={
                    "query": "MADGDSGSERGGGGGGGGGPGGFQPAPRGGGGGGGGPGGEQETQELASKRLDIQNKRFYLDVKQNAKGRFLKIAEVGAGGSKSRLTLSMAVAAEFRDSLGDFIEHYAQLGPSSPEQLAAGAEEGGGPRRALKSEFLVRENRKYYLDLKENQRGRFLRIRQTVNRGGGGFGGGPGPGGLQSGQTIALPAQGLIEFRDALAKLIDDYGGDEDELAGGPGGGAGGPGGGLYGELPEGTSITVDSKRFFFDVGCNKYGVFLRVSEVKPSYRNAITVPFKAWGKFGGAFCRYADEMKEIQERQRDKLYERRGGGSGGGDESEGEEVDED",
                    "db": "nr",
                    "program": "blastp",
                },
            )
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
