import json
import logging
import time
from typing import Any, Union

import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class WosSearchAPI:
    """
    Web of Science Search API tool provider.
    API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data
    """
    wos_api_key: str = None
    base_url: str = 'https://api.clarivate.com/apis/wos-starter/v1/documents'

    def __init__(self, api_key: str) -> None:
        """Initialize Web of Science Search API tool provider."""
        self.wos_api_key = api_key
        self.limit = 50

    @staticmethod
    def get_query(query: str, query_type: str = 'TS') -> str:
        """
        Get parameters for Web of Science Search API.
        :param query: query string
        :param query_type: query type: TI(title), AU(author), TS(title, abstract, author keywords, keywords plus), DO(doi), IS(ISSN),  PMID(PubMed ID),
        """
        assert query_type in ['TS', 'TI', 'AU', 'DO', 'IS', 'PMID'], 'Invalid query type'
        return "{}={}".format(query_type, query)

    @staticmethod
    def _process_response(response: dict) -> list[dict]:
        """
        Process response from Web of Science Search API.
        response example:

        """
        result = []
        if response and 'hits' in response:
            for wos_document in response['hits']:
                identifiers = wos_document.get('identifiers')
                if not identifiers:
                    continue
                document = {
                    'uid': wos_document.get('uid'),
                    'title': wos_document['title'],
                    'doi': identifiers.get('doi', ''),
                    # 'issn': wos_document['identifiers'].get('issn'),
                    'pmid': identifiers.get('pmid', ''),
                    # 'published_year': wos_document['source'].get('publishYear'),
                    # 'published_month': wos_document['source'].get('publishMonth'),
                    # 'types': wos_document.get('types'),
                    # 'link': wos_document['links'].get('record'),
                    # 'keywords': wos_document['keywords'].get('authorKeywords'),
                    # 'authors': [author['displayName'] for author in wos_document['names']['authors']],
                }
                result.append(document)
        return result

    def query_once(self, query: str, limit: int = 50, page: int = 1, sort_field: str = 'RS+D', db: str = 'WOK') -> tuple[int, list[dict]]:
        """
        Query Web of Science Search API once.

        Args:
            query: query string
            limit: number of results to return
            page: page number, default is 1(start from 1)
            sort_field: sort field, default is 'RS+D'(Relevance + Descending)
            db: database name, default is 'WOK'(all databases), 'WOS' for Web of Science Core Collection,
             Available values : BCI, BIOABS, BIOSIS, CCC, DIIDW, DRCI, MEDLINE, PPRN, WOK, WOS, ZOOREC
        """
        if limit <= 0:
            return 0, []
        request_str = f'{self.base_url}?q={query}&limit={limit}&page={page}&sortField={sort_field}&db={db}'
        print(f"Web of Science API request: {request_str}")
        response = requests.get(request_str, headers={'X-ApiKey': self.wos_api_key})
        response.raise_for_status()
        if response.status_code != 200:
            print(f"Web of Science API request failed: {response.json()}")
            return 0, []
        response = response.json()
        print("metadata:", response['metadata'])
        total = response['metadata']['total']
        data = self._process_response(response)
        return total, data

    def search(self, query: str, query_type: str = 'TS', num_results: int = 50, sort_field: str = 'RS+D'):
        """
        web of science api: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger

        sortField: Order by field(s). Field name and order by clause separated by '+', use A for ASC and D for DESC, ex: PY+D. Multiple values are separated by comma. Supported fields:
                    LD - Load Date
                    PY - Publication Year
                    RS - Relevance
                    TC - Times Cited
        """
        query = self.get_query(query, query_type)

        limit = min(num_results, self.limit)
        page = 1
        total, data = self.query_once(query, limit, page=page, sort_field=sort_field)

        if total == 0:
            return []

        result = data
        rest_num = min(num_results, total) - limit

        while rest_num > 0:
            limit = min(rest_num, self.limit)
            page += 1
            total, data = self.query_once(query, limit, page, sort_field)
            if total == 0:
                break

            result.extend(data)
            rest_num -= limit
            time.sleep(10)

        return result


class WOSSearchTool(BuiltinTool):
    def _invoke(self,
                user_id: str,
                tool_parameters: dict[str, Any],
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        """
            invoke tools
        """
        api_key = self.runtime.credentials['wos_api_key']
        query = tool_parameters.get('query')
        query_type = tool_parameters.get('query_type')
        limit = tool_parameters.get('limit')
        sort_field = tool_parameters.get('sort')
        if not query_type:
            query_type = 'TS'
        if not limit:
            limit = 50
        if not sort_field:
            sort_field = 'RS+D'

        result = WosSearchAPI(api_key).search(query, query_type, limit, sort_field)

        return self.create_text_message(json.dumps(result))
