import json
import logging
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class SemanticScholarBatchAPI:
    """
        A tool for searching literatures on Semantic Scholar.
        """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/batch"

    def query(self, ids: list[str], fields: str, ) -> list[dict[str, Any]]:
        """
        get details for multiple papers at once. API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/post_graph_get_papers

        Args:
            ids: a list of paper ids. supported ids are Semantic Scholar ID, DOI, arXiv IDs, PubMed IDs, and ACL Anthology IDs.
            fields: a comma separated list of fields to return. Default is 'title,abstract,authors,year'

        example:
        ids = ['DOI:10.1002/pi.5188', 'CorpusId:215416146', 'ARXIV:2106.15928', 'PMID:1234567', 'ACL:2020.acl-main.1']
        fields = 'title,abstract,authors'
        """

        if len(ids) > 500:
            raise ToolParameterValidationError('The number of papers should be less than 500')

        response = requests.post(self.base_url, json={"ids": ids}, params={"fields": fields})
        response.raise_for_status()
        response = response.json()
        result = []
        for pid, paper in zip(ids, response):
            if not paper or paper.get('abstract', None) is None:
                continue
            else:
                paper['id'] = pid
                result.append(paper)

        return result


class SemanticScholarTool(BuiltinTool):
    """
    A tool for searching literatures on Semantic Scholar.
    """

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the SemanticScholar search tool with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        ids = tool_parameters.get('ids')
        fields = tool_parameters.get('fields')

        if not ids:
            raise ToolParameterValidationError('query ids is required.')

        if not fields:
            fields = "title,abstract,externalIds"

        ids = ids.strip().split(',')
        print(f"Semantic Scholar search: {ids}")
        results = SemanticScholarBatchAPI().query(ids, fields)
        return [self.create_json_message(r) for r in results]
