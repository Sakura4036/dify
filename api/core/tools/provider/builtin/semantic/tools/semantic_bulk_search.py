import json
import logging
import time
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class SemanticBulkSearchAPI:
    """
    A tool for searching literatures on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/search/bulk?"
    switch_grammar = {
        "AND": '+',
        "OR": '|',
        "NOT": '-',
    }

    def check_query(self, query: str):
        for key, value in self.switch_grammar.items():
            query = query.replace(key, value)
        return f"({query})"

    def check_type(self, types: str):
        if not types or types == 'All':
            return ''
        if types == 'Article':
            return 'JournalArticle'
        if types == 'Review':
            return 'Review'
        else:
            raise ToolParameterValidationError(f"Invalid publication type: {types}")

    def query_once(self, query: str,
                   year: str = '',
                   document_type: str = '',
                   fields_of_study: str = '',
                   fields: str = '',
                   token: str = None,
                   filtered: bool = False) -> tuple:
        """
        Query once for the semantic scholar bulk search.
        API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_bulk_search

        return example:
        {
            "total": 1,
            "token": "xxx",
            "data": [
                {
                    "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
                    "corpusId": 2314124,
                    "externalIds": {},
                    "url": "https://www.semanticscholar.org/paper/649def34f8be52c8b66281af98ae884c09aef38b",
                    "title": "Construction of the Literature Graph in Semantic Scholar",
                    "abstract": "We describe a deployed scalable system ...",
                    ...
                }
            ]
        }
        """
        url = f"{self.base_url}query={query}"
        if fields_of_study:
            url += f"&fieldsOfStudy={fields_of_study}"
        if year:
            url += f"&year={year}"
        if fields:
            url += f"&fields={fields}"
        if document_type:
            url += f"&publicationTypes={document_type}"
        if token:
            # token is used to get the next page of results
            url += f"&token={token}"

        print(f"Semantic Scholar bulk search: {url}")
        response = requests.get(url, stream=False)
        response.raise_for_status()
        if response.status_code != 200:
            return 0, []
        response = response.json()
        total = response['total']

        data = []
        for paper in response['data']:
            if not paper:
                continue
            if filtered and 'abstract' in fields and paper.get('abstract', None) is None:
                continue
            data.append(paper)

        token = response.get('token', None)
        return total, data, token

    def query(self, query: str,
              year: str = '',
              document_type: str = '',
              fields_of_study: str = '',
              fields: str = '',
              num_results: int = 50,
              filtered: bool = False) -> dict | list[dict]:
        """
        Paper bulk search on Semantic Scholar.
        """
        query = self.check_query(query)
        document_type = self.check_type(document_type)

        total, data, token = self.query_once(query, year, document_type, fields_of_study, fields, filtered=filtered)

        if total == 0:
            data = [{}]
            return data

        if len(data) >= num_results:
            # if the number of results is greater than or equal to the requested number of results, return the result
            result = data[:num_results]
        else:
            # if the number of results is less than the requested number of results, get the next page of results
            result = data
            rest_num_results = min(num_results, total) - len(data)  # the maximum number of rest results that can be obtained

            while rest_num_results > 0:
                total, data, token = self.query_once(query, year, document_type, fields_of_study, fields, token=token, filtered=filtered)
                if token is None:
                    break
                result.extend(data)
                rest_num_results -= len(data)
                # sleep for 15 seconds to avoid rate limit
                time.sleep(15)
        print(f"Total results: {total},  result length: {len(result)}")
        return result


class SemanticBulkSearchTool(BuiltinTool):

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
            fields_of_study = ''
        year = tool_parameters.get('year')
        if not year:
            year = '1960-'
        fields = tool_parameters.get('fields')
        if not fields:
            fields = "title,abstract,externalIds,openAccessPdf,year,publicationTypes"
        document_type = tool_parameters.get('document_type', 'All')
        num_results = tool_parameters.get('num_results')
        if not num_results:
            num_results = 50
        filtered = tool_parameters.get('filtered', False)

        results = SemanticBulkSearchAPI().query(query, year, document_type, fields_of_study, fields, num_results, filtered)
        return [self.create_json_message(r) for r in results]
