import json
from typing import Any

import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool


class SearXNGSearchResults(dict):
    """Wrapper for search results."""

    def __init__(self, data: str):
        super().__init__(json.loads(data))
        self.__dict__ = self

    @property
    def results(self) -> Any:
        return self.get("results", [])


class SearXNGSearchTool(BuiltinTool):
    """
    Tool for performing a search using SearXNG engine.
    """

    """
    "categories":["general","social media","files","apps","it","software wikis","images","science",
    "scientific publications","music","videos","web","news","repos",
    "other","packages","weather","map","dictionaries","lyrics","cargo","movies","translate",
    "radio","q&a","wikimedia"]
    """
    SEARCH_TYPE: dict = {
        "page": "general",
        "news": "news",
        "image": "images",
        "science": "science",
        # "video": "videos",
        # "file": "files"
    }

    LINK_FILED: dict = {
        "page": "url",
        "news": "url",
        "image": "img_src",
        "science": "url",
        # "video": "iframe_src",
        # "file": "magnetlink"
    }
    TEXT_FILED: dict = {
        "page": "content",
        "news": "content",
        "image": "img_src",
        "science": "content",
        # "video": "iframe_src",
        # "file": "magnetlink"
    }

    def _invoke_query(self, user_id: str, host: str, query: str, search_type: str, result_type: str, topK: int = 5) -> ToolInvokeMessage:
        """Run query and return the results."""

        search_type = search_type.lower()
        if search_type not in self.SEARCH_TYPE.keys():
            search_type = "page"

        response = requests.get(host, params={
            "q": query,
            "format": "json",
            "categories": self.SEARCH_TYPE[search_type]
        })

        if response.status_code != 200:
            raise Exception(f'Error {response.status_code}: {response.text}')

        search_results = SearXNGSearchResults(response.content.decode(encoding='utf-8')).results
        print("search_results len: ", len(search_results))
        search_results = search_results[:topK]

        if result_type == 'link':
            if search_type == "page" or search_type == "news":
                results = [{
                    "title": r.get("title", ""),
                    "url": r.get(self.LINK_FILED[search_type], "")
                } for r in search_results]
            else:
                results = [{
                    "url": r.get(self.LINK_FILED[search_type], ""),
                } for r in search_results]
        else:
            results = [{
                "title": r.get("title", ""),
                "content": r.get(self.TEXT_FILED[search_type], ""),
                "url": r.get(self.LINK_FILED[search_type], ""),
            } for r in search_results]

        # return self.create_json_message(results)
        return self.create_text_message(json.dumps(results))

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage:
        """
        Invoke the SearXNG search tool.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool invocation.

        Returns:
            ToolInvokeMessage: The result of the tool invocation.
        """

        host = self.runtime.credentials.get('searxng_base_url', None)

        query = tool_parameters.get('query', None)
        if not query:
            raise ToolParameterValidationError('query is required.')

        num_results = min(tool_parameters.get('num_results', 10), 30)
        search_type = tool_parameters.get('search_type', 'page') or 'page'
        result_type = tool_parameters.get('result_type', 'text') or 'text'

        return self._invoke_query(
            user_id=user_id,
            host=host,
            query=query,
            search_type=search_type,
            result_type=result_type,
            topK=num_results)
