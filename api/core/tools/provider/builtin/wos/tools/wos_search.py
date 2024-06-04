import json
import logging
from typing import Any, Union

import requests

from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class WosSearchAPI:
    """
    Web of Science Search API tool provider.
    """
    wos_api_key: str = None

    def __init__(self, api_key: str) -> None:
        """Initialize Web of Science Search API tool provider."""
        self.wos_api_key = api_key

    @staticmethod
    def get_query(query: str, query_type: str = 'TS') -> str:
        """
        Get parameters for Web of Science Search API.
        :param query: query string
        :param query_type: query type: TI(title), AU(author), TS(title, abstract, author keywords, keywords plus), DO(doi), IS(ISSN),  PMID(PubMed ID),
        """
        assert query_type in ['TS', 'TI', 'AU', 'DO', 'IS', 'PMID'], 'Invalid query type'
        return "{}={}".format(query_type, query)

    def get_request(self, query: str, limit: int = 100, page: int = 1, sort_field: str = 'RS+D'):
        """
        web of science api: https://api.clarivate.com/swagger-ui/?apikey=none&url=https%3A%2F%2Fdeveloper.clarivate.com%2Fapis%2Fwos-starter%2Fswagger

        sortField: Order by field(s). Field name and order by clause separated by '+', use A for ASC and D for DESC, ex: PY+D. Multiple values are separated by comma. Supported fields:
                    LD - Load Date
                    PY - Publication Year
                    RS - Relevance
                    TC - Times Cited
        """
        response = {}

        for p in range(1, page + 1):
            request_str = f'https://api.clarivate.com/apis/wos-starter/v1/documents?q={query}&limit={limit}&page={p}&db=WOS&sortField={sort_field}'
            logger.debug(f'request_str: {request_str} ')
            try:
                initial_request = requests.get(request_str, headers={'X-ApiKey': self.wos_api_key})
                initial_json = initial_request.json()
                logger.debug(f'initial_json: {initial_json}')
            except Exception as e:
                if not response:
                    logger.error(f'Error in request: {e}')
                    raise e
                else:
                    return response

            response.update(initial_json)

        return response

    @staticmethod
    def _process_response(response: dict) -> list[dict]:
        result = []
        if response and 'hits' in response:
            for wos_document in response['hits']:
                document = {
                    'uid': wos_document.get('uid'),
                    'title': wos_document['title'],
                    'doi': wos_document['identifiers'].get('doi'),
                    'issn': wos_document['identifiers'].get('issn'),
                    'pmid': wos_document['identifiers'].get('pmid'),
                    'published_year': wos_document['source'].get('publishYear'),
                    'published_month': wos_document['source'].get('publishMonth'),
                    'types': wos_document.get('types'),
                    'link': wos_document['links'].get('record'),
                    'keywords': wos_document['keywords'].get('authorKeywords'),
                    'authors': [author['displayName'] for author in wos_document['names']['authors']],
                }
                result.append(document)

        return result

    def run(self, query: str, query_type, limit: int = 100, page: int = 1, sort_field: str = 'RS+D') -> list:
        """Run query through Web of Science Search API and parse result."""
        query = self.get_query(query, query_type)
        request = self.get_request(query, limit=limit, page=page, sort_field=sort_field)
        return self._process_response(request)


class WOSSearchTool(BuiltinTool):
    def _invoke(self,
                user_id: str,
                tool_parameters: dict[str, Any],
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        """
            invoke tools
        """
        query = tool_parameters['query']
        query_type = tool_parameters.get('query_type', 'TS')

        limit = tool_parameters.get('limit', 50)
        page = tool_parameters.get('page', 1)
        sort_field = tool_parameters.get('sort', 'PY+D')

        api_key = self.runtime.credentials['wos_api_key']

        logger.debug(f"query: {query}")
        logger.debug(f"query_type: {query_type}")

        result = WosSearchAPI(api_key).run(query, query_type, limit, page, sort_field)

        if not result:
            result = 'No results found'
        else:
            result = ' <eos> '.join([json.dumps(doc) for doc in result])
        # save search result to variable, use self.get_variable('wos_search_result_{user_id}') to get the result
        return self.create_text_message(text=result, save_as=f'wos_search_result_{user_id}')
