from typing import Any
import os
import time
from core.tools.errors import ToolProviderCredentialValidationError
from core.tools.provider.builtin_tool_provider import BuiltinToolProviderController


class ZhiHuiYaProvider(BuiltinToolProviderController):

    def get_bearer_token(self, credentials: dict[str, Any]) -> str:
        token = os.environ.get("ZHIHUIYA_BEARER_TOKEN")
        if token is None:
            import requests

            url = "https://connect.zhihuiya.com/oauth/token"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = 'grant type=client credentials'
            # auth = (credentials['api_key'], "ZopZtkrmMYTcDNc2TalqDnzbyH4Uo6hC2AmiOOK0G9wCLUlhAPEzr4C0WPulXZVT")
            auth = (credentials['api_key'], credentials['client_secret'])

            response = requests.post(url, headers=headers, data=data, auth=auth)
            response.raise_for_status()
            response = response.json()
            if response['status']:
                token = response['data']['token']
            else:
                raise Exception(response.dumps())

            os.environ["ZHIHUIYA_BEARER_TOKEN"] = token
            # token expires in 25 minutes
            os.environ["ZHIHUIYA_BEARER_TOKEN_EXPIRE"] = str(time.time() + 1500)
        else:
            if float(os.environ["ZHIHUIYA_BEARER_TOKEN_EXPIRE"]) < time.time():
                # token expired
                del os.environ["ZHIHUIYA_BEARER_TOKEN"]
                del os.environ["ZHIHUIYA_BEARER_TOKEN_EXPIRE"]
                token = self.get_bearer_token(credentials)

        return token

    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            import requests
            url = "https://connect.zhihuiya.com/search/patent/query-search-count"

            params = {
                "apikey": credentials["api_key"]
            }

            payload = {
                "query_text": "TACD: virtual reality",
                "collapse_by": "PBD",
                "collapse_type": "DOCDB",
                "collapse_order": "LATEST"
            }
            token = self.get_bearer_token(credentials)
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer {}".format(token)
            }

            response = requests.request("POST", url, params=params, json=payload, headers=headers)
            response.raise_for_status()
            print(response.text)
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
