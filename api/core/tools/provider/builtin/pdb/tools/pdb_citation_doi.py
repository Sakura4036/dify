import json
import logging
from typing import Any
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class PDBCitationDOIsTool(BuiltinTool):
    """
    A tool to retrieve citation information from the protein database by pdb id.
    """
    entry_base_url: str = "https://data.rcsb.org/rest/v1/core/entry/"
    pubmed_base_url: str = "https://data.rcsb.org/rest/v1/pubmed/entry/"
    semantic_base_url: str = "https://api.semanticscholar.org/graph/v1/paper/batch"
    semantic_doi_fields = 'title,abstract,authors,year,citationCount,influentialCitationCount'

    def get_pdb_citation_doi(self, entry_id: str, mode: str = 'all') -> list[str]:
        url = f"{self.entry_base_url}{entry_id}"
        # print(f"Querying RCSB PDB: {url}")
        response = requests.get(url)
        response.raise_for_status()
        if response.status_code != 200:
            # print(f"Error querying RCSB PDB: {response.json()}")
            return []
        else:
            response = response.json()
            # print(f"Retrieved response: {response}")
            if 'citation' in response:
                citations = response['citation']
            elif 'rcsb_primary_citation' in response:
                citations = [response['rcsb_primary_citation']]
            else:
                return []
            # print(f"Retrieved citations: {citations}")
            # Filter primary citation
            if mode == 'primary':
                for citation in citations:
                    if citation['id'] == 'primary' or citation['rcsb_is_primary'].upper() == 'Y' or citation['id'] == '0':
                        citations = [citation]
                        break

            # Filter out citations without DOI
            doi = []
            for citation in citations:
                if 'pdbx_database_id_doi' in citation:
                    doi.append("DOI:"+citation['pdbx_database_id_doi'].lower())
            return doi

    def query(self, entry_id: str, mode: str = 'all') -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        get protein info from RCSB PDB. API documentation: https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getEntryById and https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getPubmedByEntryId

        Args:
            entry_id (str): The ID of the protein entry. ex: 4HHB
            mode (str): The mode of the query. 'all' to get all citation infos, 'primary' to get only primary citation
        """
        doi = self.get_pdb_citation_doi(entry_id, mode)
        doi = ', '.join(doi)
        return self.create_text_message(doi)

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the PDBCitationsTools with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        entry_id = tool_parameters.get('entry_id')
        mode = tool_parameters.get('mode')

        if not entry_id:
            return self.create_text_message('Please provide a entry_id.')

        if not mode:
            mode = 'all'

        return self.query(entry_id, mode)
