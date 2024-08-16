import traceback

from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin.chrome_downloader.tools.pdf_download import PDFDownloaderTool
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class ChromeDownloaderProvider(BuiltinToolProviderController):
    def _validate_credentials(self, credentials: dict) -> None:
        try:
            tool = PDFDownloaderTool().fork_tool_runtime(
                runtime={
                    "credentials": credentials,
                })
            print("credentials", credentials)

            result = tool.invoke(
                user_id='',
                tool_parameters={
                    "doi": "10.1038/s41467-023-43214-1",
                    "title": "A knowledge-guided pre-training framework for improving molecular representation learning",
                    "url": "https://www.nature.com/articles/s41467-023-43214-1"
                },
            )
            print("result", result)
        except Exception as e:
            traceback.print_exc()
            raise ToolProviderCredentialValidationError(str(e))
