import json
import logging
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class SemanticRelevanceSearchTool(BuiltinTool):
    """
    A tool for searching literatures on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/search?"

    def query_once(self, query: str, fields_of_study: str, year: str, fields: str, offset: int = 0, limit: int = 100) -> tuple:
        url = f"{self.base_url}query={query}&year={year}&fieldsOfStudy={fields_of_study}&fields={fields}&offset={offset}&limit={limit}"

        response = requests.get(url, stream=False)
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

    def query(self, query: str, fields_of_study: str, year: str, fields: str, num_results: int = 100) -> ToolInvokeMessage | list[
        ToolInvokeMessage]:
        """
        Paper relevance search on Semantic Scholar. API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_relevance_search
        """
        # url = f"{self.base_url}query={query}&year={year}&fields={fields}&openAccessPdf"
        limit = min(num_results, 100)
        total, data = self.query_once(query, fields_of_study, year, fields, limit=limit)
        if total == 0:
            return self.create_text_message('No results found.')
        else:
            if limit < 100 or total < 100:
                # the total number of results is less than 100, return all results
                return self.create_text_message(json.dumps(data))
            else:
                # the total number of results is more than 100, and num_results is more than 100
                result = data
                for i in range(1, num_results // 100 + 1):
                    # use the offset to get the rest of the results
                    num_results -= 100
                    offset = i * 100
                    total, data = self.query_once(query, fields_of_study, year, fields, offset=offset, limit=min(num_results, 100))
                    result.extend(data)
                return self.create_text_message(json.dumps(result[:num_results]))

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the SemanticScholar search tool with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        query = tool_parameters.get('query', '')
        fields_of_study = tool_parameters.get('fields_of_study', 'Medicine,Biology,Chemistry')
        year = tool_parameters.get('year', '1980-')
        fields = tool_parameters.get('fields', 'title,abstract,authors,year,citationCount,influentialCitationCount')
        num_results = tool_parameters.get('num_results', 50)

        if not query:
            return self.create_text_message('Please provide a list of paper ids.')
        try:
            return self.query(query, fields_of_study, year, fields, num_results)
        except Exception as e:
            logger.error(f'Error invoking Semantic Scholar tool: {e}')
            return self.create_text_message(f'Error invoking Semantic Scholar tool: {e}')
