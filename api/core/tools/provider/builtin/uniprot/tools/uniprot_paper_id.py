import json
import logging
from typing import Any, Optional
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class UniProtPaperIDTool(BuiltinTool):
    """
    A tool for searching protein information on UniProt.
    """
    base_url: str = "https://rest.uniprot.org/uniprotkb/search?query={}&size={}&format=json&compressed=false"

    @staticmethod
    def get_paper_id_from_reference(reference: dict) -> str:
        """
        Extracts the paper ID from a reference dictionary.
        example reference:
        {
            "citation": {
                "authors": ["Hirayama H.", "Takaki Y.", "Takai K."],
                "citationType": "submission",
                "id": "CI-9IO9BFCQP0L3O",
                "publicationDate": "JUN-2020",
                "submissionDatabase": "EMBL/GenBank/DDBJ databases",
                "title": "Genomic insights into marine methnotrophic bacteria enriched with methan reactor cultivation."
            },
            "evidences": [{
                    "evidenceCode": "ECO:0000313",
                    "id": "UP000595511",
                    "source": "Proteomes"
                }
            ],
            "referenceNumber": 1,
            "referencePositions": ["NUCLEOTIDE SEQUENCE [LARGE SCALE GENOMIC DNA]"]
        }
        """
        ref_id = ''
        if 'citationCrossReferences' in reference['citation']:
            refs = reference['citation']['citationCrossReferences']
            for ref in refs:
                if not ref and ref['database'] == 'PubMed':
                    ref_id = f"PMID:{ref['id']}"
                elif ref['database'] == 'DOI':
                    ref_id = f"DOI:{ref['id']}"
        return ref_id

    @staticmethod
    def get_paper_ids_from_references(references: list[dict]) -> list[str]:
        """
        Extracts the paper IDs from a list of reference dictionaries.
        """
        paper_ids = []
        for reference in references:
            paper_id = UniProtPaperIDTool.get_paper_id_from_reference(reference)
            # only add the paper ID if it is not empty
            if paper_id:
                paper_ids.append(paper_id)

        return paper_ids

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
                return self.create_text_message(f'Error querying UniProt: {response.text}')
            response = response.json()
            paper_ids = []

            if response.get('results', None) is None:
                # response is a dictionary for one protein when the query is an accession number, like "accession:P33993"
                if response.get('references', None) is not None:
                    references = response.get('references', [])
                    paper_ids = self.get_paper_ids_from_references(references)
            else:
                result = response['results']
                if isinstance(result, list):
                    # response is a list of dictionaries when the query is a key word or an UniProt ID, like "P05067"
                    for protein in result:
                        references = protein.get('references', [])
                        paper_ids.extend(self.get_paper_ids_from_references(references))
                else:
                    references = result.get('references', [])
                    paper_ids = self.get_paper_ids_from_references(references)
            paper_ids = list(set(paper_ids))
            return self.create_text_message(','.join(paper_ids))

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
            return self.create_text_message('Please input query')

        return self.query(query, size)
