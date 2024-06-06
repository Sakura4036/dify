import json
import logging
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class SemanticScholarTool(BuiltinTool):
    """
    A tool for searching literatures on Semantic Scholar.
    """
    base_url: str = "https://api.semanticscholar.org/graph/v1/paper/batch"

    def query(self, ids: list[str], fields: str, ) -> ToolInvokeMessage | list[
        ToolInvokeMessage]:
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
            return self.create_text_message('The number of papers should be less than 500')

        with requests.post(self.base_url, json={"ids": ids}, params={"fields": fields}) as response:
            if response.status_code != 200:
                return self.create_text_message(f'Error querying Semantic Scholar: {response.json()["error"]}')
            response = response.json()
            result = []
            for pid, paper in zip(ids, response):
                if paper['abstract'] is None:
                    continue
                else:
                    paper['id'] = pid
                    result.append(paper)

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
        ids = tool_parameters.get('ids', '')
        fields = tool_parameters.get('fields', 'title,abstract,authors,year,citationCount,influentialCitationCount')

        if not ids:
            return self.create_text_message('Please provide a list of paper ids.')
        try:
            ids = ids.split(',')
            return self.query(ids, fields)
        except Exception as e:
            logger.error(f'Error invoking Semantic Scholar tool: {e}')
            return self.create_text_message(f'Error invoking Semantic Scholar tool: {e}')
