# !/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
@File     : query.py
@Time     : 2024/8/16 10:03
@Author   : Hjw
@License  : (C)Copyright 2018-2025
"""
import time
import requests
from typing import Any, Union, List

from core.tools.errors import ToolParameterValidationError
from core.tools.provider.builtin.crossref.tools.utils import convert_time_str_to_seconds, get_basic_info
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage


class CrossRefQueryTitleAPI:
    # doc: https://github.com/CrossRef/rest-api-doc
    query_url_template: str = "https://api.crossref.org/works?query.bibliographic={query}&rows={rows}&offset={offset}&sort={sort}&order={order}&mailto={mailto}"
    rate_limit: int = 50
    rate_interval: float = 1
    max_limit: int = 1000

    def __init__(self, mailto: str):
        self.mailto = mailto

    def _query(self, query: str, rows: int = 3, offset: int = 0, sort: str = 'relevance', order: str = 'desc',
               fuzzy_query: bool = False, return_type: str = 'basic') -> List[dict]:
        url = self.query_url_template.format(query=query, rows=rows, offset=offset, sort=sort, order=order, mailto=self.mailto)
        response = requests.get(url)
        response.raise_for_status()
        rate_limit = int(response.headers['x-ratelimit-limit'])
        rate_interval = convert_time_str_to_seconds(response.headers['x-ratelimit-interval'])

        self.rate_limit = rate_limit
        self.rate_interval = rate_interval

        response = response.json()
        if response['status'] != 'ok':
            return []

        message = response['message']
        print("total_results", message["total-results"])
        print("message", len(message['items']))
        print("fuzzy_query", fuzzy_query)
        if fuzzy_query:
            # fuzzy query return all items
            if return_type == 'all':
                return message['items']
            if return_type == 'basic':
                return [get_basic_info(p) for p in message['items']]
        else:
            for paper in message['items']:
                title = paper['title'][0]
                if title.lower() != query.lower():
                    continue
                if return_type == 'all':
                    return [paper]
                if return_type == 'basic':
                    return [get_basic_info(paper)]

            return []

    def query(self, query: str, rows: int = 3, sort: str = 'relevance', order: str = 'desc',
              fuzzy_query: bool = False, return_type: str = 'basic') -> List[dict]:
        rows = min(rows, self.max_limit)
        if rows > self.rate_limit:
            query_times = rows // self.rate_limit + 1
            results = []

            for i in range(query_times):
                result = self._query(query, rows=self.rate_limit, offset=i * self.rate_limit, sort=sort, order=order,
                                     fuzzy_query=fuzzy_query, return_type=return_type)
                if fuzzy_query:
                    results.extend(result)
                else:
                    if result:
                        return result
                time.sleep(self.rate_interval)
            return results
        else:
            return self._query(query, rows, sort=sort, order=order, fuzzy_query=fuzzy_query, return_type=return_type)


class CrossRefQueryTitleTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        query = tool_parameters.get('query')
        fuzzy_query = tool_parameters.get('fuzzy_query', False)
        rows = tool_parameters.get('rows', 3)
        sort = tool_parameters.get('sort', 'relevance')
        order = tool_parameters.get('order', 'desc')
        return_type = tool_parameters.get('return_type', 'basic')
        if return_type not in ['basic', 'all']:
            raise ToolParameterValidationError('return_type must be "basic" or "all".')
        mailto = self.runtime.credentials['mailto']

        result = CrossRefQueryTitleAPI(mailto).query(query, rows, sort, order, fuzzy_query, return_type)

        return [self.create_json_message(r) for r in result]
