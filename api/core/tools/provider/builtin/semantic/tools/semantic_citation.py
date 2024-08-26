# !/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
@File     : semantic_citation.py
@Time     : 2024/8/21 14:56
@Author   : Hjw
@License  : (C)Copyright 2018-2025
"""
import time

import requests
from typing import Any
import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool


class SemanticCitationAPI:
    citation_api: str = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
    reference_api: str = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references"
    max_limit: int = 1000

    def get_citations(self, paper_id: str, params: dict[str, Any] = None) -> list[dict]:
        """
        Get citations of a paper
        :param paper_id: paper id
        :param params: query params: fields, offset, limit
        :return: response
        """
        url = self.citation_api.format(paper_id=paper_id)
        response = requests.get(url, params=params)
        time.sleep(1)
        response.raise_for_status()

        data = response.json()['data']
        citations = []
        for paper in data:
            citations.append(paper['citingPaper'])

        return citations

    def get_references(self, paper_id: str, params: dict[str, Any] = None) -> list[dict]:
        """
        Get references of a paper
        :param paper_id: paper id
        :param params: query params: fields, offset, limit
        :return: response
        """
        url = self.reference_api.format(paper_id=paper_id)
        response = requests.get(url, params=params)
        time.sleep(1)
        response.raise_for_status()

        data = response.json()['data']
        references = []
        for paper in data:
            references.append(paper['citedPaper'])

        return references

    def get_citations_references(self, paper_id: str, fields: str = '', offset: int = 0, limit: int = 100, citation: bool = True,
                                 reference: bool = False) -> dict:
        if limit > self.max_limit:
            limit = self.max_limit

        if not fields:
            fields = "title,abstract,publicationTypes,publicationDate,journal,externalIds,referenceCount,citationCount,openAccessPdf"
        params = {
            "offset": offset,
            "limit": limit,
            "fields": fields
        }
        citations = []
        references = []
        if citation:
            citations = self.get_citations(paper_id, params)
        if reference:
            references = self.get_references(paper_id, params)

        return {"citations": citations, "references": references}


class SemanticCitationTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        paper_id = tool_parameters.get('paper_id')
        if not paper_id:
            raise ToolParameterValidationError("paper_id is required")
        fields = tool_parameters.get('fields')
        limit = tool_parameters.get('limit', 50)
        citation = tool_parameters.get('citation', True)
        reference = tool_parameters.get('reference', True)
        result = SemanticCitationAPI().get_citations_references(paper_id, fields, 0, limit, citation, reference)
        return self.create_json_message(result)
