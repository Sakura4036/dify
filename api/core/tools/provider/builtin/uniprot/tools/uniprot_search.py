import json
import logging
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class UniProtSearchTool(BuiltinTool):
    """
    A tool for searching protein information on UniProt.
    """
    base_url: str = "https://rest.uniprot.org/uniprotkb/search?query={}&size={}&format=json&compressed=false"

    def query(self, query: str, size: int = 500) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Performs an uniprot search. Query strings must satisfy the query syntax:https://www.uniprot.org/help/query-fields.

        Args:
            query: a plaintext search query
            size: the number of results to return
        """
        url = self.base_url.format(query, size)
        logger.debug(f'Querying UniProt with URL: {url}')
        with requests.get(url, stream=False) as response:
            response.raise_for_status()
            if response.status_code != 200:
                print(response.text)
                return [self.create_json_message([])]
            response = response.json()

            # response is a dictionary for one protein when the query is an accession number, like "P33993"
            if response.get('results', None) is None:
                if response.get('references', None) is not None:
                    references = response.get('references', [])
                    return [self.create_json_message(ref) for ref in references]
                else:
                    return [self.create_json_message([])]
            else:
                result = response['results']
                return_messages = []
                if isinstance(result, list):
                    for protein in result:
                        references = protein.get('references', [])
                        return [self.create_json_message(ref) for ref in references]
                    return return_messages
                else:
                    references = result.get('references', [])
                    return [self.create_json_message(ref) for ref in references]

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the UniProt search tool with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        query = tool_parameters.get('query', '')
        size = tool_parameters.get('num_results', 50)

        if not query:
            raise ToolParameterValidationError('query is required.')

        return self.query(query, size)