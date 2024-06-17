import json
import logging
import time
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class SemanticRelevanceSearchTool(BuiltinTool):
    """
    A tool for searching literatures on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/search?"
    max_num_query_once: int = 100

    def query_once(self, query: str, fields_of_study: str, year: str, fields: str, offset: int = 0, limit: int = 50) -> tuple:
        if limit <= 0:
            return 0, []
        url = f"{self.base_url}query={query}&year={year}&fieldsOfStudy={fields_of_study}&fields={fields}&offset={offset}&limit={limit}"
        print(f"Querying Semantic Scholar: {url}")
        response = requests.get(url, stream=False)
        response.raise_for_status()
        if response.status_code != 200:
            return 0, []
        response = response.json()
        total = response['total']
        data = []
        for paper in response['data']:
            if paper['abstract'] is None:
                continue
            else:
                data.append(paper)
        return total, data

    def query(self, query: str, fields_of_study: str, year: str, fields: str, num_results: int = 50) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Paper relevance search on Semantic Scholar. API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_relevance_search
        """
        limit = min(num_results, self.max_num_query_once)
        total, data = self.query_once(query, fields_of_study, year, fields, limit=limit)

        if total == 0:
            return self.create_text_message('No results found.')

        result = data
        rest_num_results = min(num_results, total) - len(data)
        offset = limit

        while rest_num_results > 0 and offset < num_results:
            total, data = self.query_once(query, fields_of_study, year, fields, offset=offset, limit=min(rest_num_results, self.max_num_query_once))

            if total == 0:
                break

            result.extend(data)
            offset += self.max_num_query_once
            rest_num_results -= len(data)

            # sleep for 15 seconds to avoid rate limit
            time.sleep(15)

        return self.create_text_message(json.dumps(result))

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the SemanticScholar search tool with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        query = tool_parameters.get('query')
        if not query:
            raise ToolParameterValidationError('query is required.')
        fields_of_study = tool_parameters.get('fields_of_study')
        if not fields_of_study:
            fields_of_study = 'Medicine,Biology,Chemistry'
        year = tool_parameters.get('year')
        if not year:
            year = '1900-'
        fields = tool_parameters.get('fields')
        if not fields:
            fields = 'title,abstract,year,citationCount,influentialCitationCount'
        num_results = tool_parameters.get('num_results', 50)
        if not num_results:
            num_results = 50

        return self.query(query, fields_of_study, year, fields, num_results)
