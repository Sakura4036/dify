import json
import logging
from typing import Any
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class PDBCitationsTool(BuiltinTool):
    """
    A tool to retrieve citation information from the protein database by pdb id.
    """
    entry_base_url: str = "https://data.rcsb.org/rest/v1/core/entry/"
    pubmed_base_url: str = "https://data.rcsb.org/rest/v1/pubmed/entry/"
    semantic_base_url: str = "https://api.semanticscholar.org/graph/v1/paper/batch"
    semantic_doi_fields = 'title,abstract,authors,year,citationCount,influentialCitationCount'

    def get_info_by_doi(self, dois: list[str], fields: str = '') -> list[dict]:
        if not fields:
            fields = self.semantic_doi_fields
        ids = [f"DOI:{doi}" for doi in dois]

        with requests.post(self.semantic_base_url, json={"ids": ids}, params={"fields": fields}) as response:
            if response.status_code != 200:
                print(f"Error querying Semantic Scholar: {response.json()['error']}")
                return []
            response = response.json()

            return response

    def get_pdb_citations(self, entry_id: str, mode: str = 'all') -> list[dict]:
        url = f"{self.entry_base_url}{entry_id}"
        print(f"Querying RCSB PDB: {url}")
        response = requests.get(url)
        response.raise_for_status()
        if response.status_code != 200:
            print(f"Error querying RCSB PDB: {response.json()}")
            return []
        else:
            response = response.json()
            print(f"Retrieved response: {response}")
            if 'citation' in response:
                citations = response['citation']
            elif 'rcsb_primary_citation' in response:
                citations = [response['rcsb_primary_citation']]
            else:
                return []
            print(f"Retrieved citations: {citations}")
            # Filter primary citation
            if mode == 'primary':
                for citation in citations:
                    if citation['id'] == 'primary' or citation['rcsb_is_primary'].upper() == 'Y' or citation['id'] == '0':
                        citations = [citation]
                        break

            # Filter out citations without DOI
            doi_citations = []
            for citation in citations:
                if 'pdbx_database_id_doi' in citation:
                    doi_citations.append({
                        'is_primary': citation['rcsb_is_primary'],
                        'doi': citation['pdbx_database_id_doi'].lower()
                    })
            print(f"Retrieved DOIs: {doi_citations}")
            citations = doi_citations
            dois = [citation['doi'] for citation in citations]

            semantic_scholar_infos = self.get_info_by_doi(dois)

            for citation, info in zip(citations, semantic_scholar_infos):
                citation.update(info)
            # Filter out citations without abstract
            citations = [citation for citation in citations if citation['abstract']]
            print(f"Retrieved citations with abstract: {citations}")
            return citations

    def get_pubmed_abstract(self, entry_id: str) -> dict:
        url = f"{self.pubmed_base_url}{entry_id}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error querying RCSB PDB: {response.json()}")
            return {}
        else:
            response = response.json()
            return {
                'pubmed_id': response['rcsb_pubmed_container_identifiers']['pubmed_id'],
                'abstract': response['rcsb_pubmed_abstract_text'],
                'doi': response['rcsb_pubmed_doi'].lower(),
            }

    def query(self, entry_id: str, mode: str = 'all') -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        get protein info from RCSB PDB. API documentation: https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getEntryById and https://data.rcsb.org/redoc/index.html#tag/Entry-Service/operation/getPubmedByEntryId

        Args:
            entry_id (str): The ID of the protein entry. ex: 4HHB
            mode (str): The mode of the query. 'all' to get all citation infos, 'primary' to get only primary citation
        """
        result = self.get_pdb_citations(entry_id, mode)
        return self.create_text_message(json.dumps(result))

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
            raise ToolParameterValidationError('Please provide a entry_id.')
        if not mode:
            mode = 'all'

        return self.query(entry_id, mode)
