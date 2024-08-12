import json
import time
import requests
from typing import List, Any, Union
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.provider.builtin.zhihuiya.zhihuiya import ZhiHuiYaProvider
from core.tools.tool.builtin_tool import BuiltinTool


class PatentQueryAPI:
    """
    zhihuiya patent query api P002
    doc: https://open.zhihuiya.com/open-api-data/docs/1a0fc47f267348a3a92f8be39f0303dc
    """
    api_key = ""
    api_url = "https://connect.zhihuiya.com/search/patent/query-search-patent/v2"
    max_limit = 100
    max_offset = 1000
    interval = 1
    query_template = "TACD:{}"

    def __init__(self, credentials: dict):
        self.api_key = credentials["api_key"]
        self.token = ZhiHuiYaProvider().get_bearer_token(credentials)

    def query_once(self, query: str, limit: int = 50, offset: int = 0, stemming: int = 0, sort: List[dict] = None,
                   collapse_type: str = None, collapse_by: str = None, collapse_order: str = None) -> tuple[int, list[dict]]:
        """
        get data from zhihuiya patent query api once
        :param query: query string
        :param limit: limit of data
        :param offset: offset of data
        :param stemming: 是否开启截词：开启截词，在保留原词的同时，并扩展其对应的单复数及时态
        :param sort: 字段排序, [{"field": "field_name", "order": "asc"}].
            field support: "PBDT_YEARMONTHDAY", "apply_date", "ISD","SCORE".
            order support: "asc", "desc"
        :param collapse_type: 选择专利去重条件, 如：ALL不去重、APNO按申请号去重、DOCDB按简单同族去重、INPADOC按inpadoc同族去重，以及EXTEND按patsnap同族去重，空值默认为ALL
        :param collapse_by: 选择专利去重的排序字段，如：APD按申请日排序、PBD按公开日排序、AUTHORITY按受理局排序，以及SCORE按照查询相关性排序
        :param collapse_order: 选择专利去重的排序顺序，如果collapse_type等于APNO，collapse_by等于APD或PBD，collapse_order的有效值应该为OLDEST或LATEST
        """
        if limit <= 0:
            return 0, []

        params = {
            "apikey": self.api_key
        }
        payload = {
            "sort": sort,
            "limit": limit,
            "offset": offset,
            "stemming": stemming,
            "query_text": query,
            "collapse_type": collapse_type,
            "collapse_by": collapse_by,
            "collapse_order": collapse_order,
            "collapse_order_authority": [
                "CN",
                "US",
                "EP",
                "JP",
                "KR"
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer {}".format(self.token)
        }

        response = requests.request("POST", self.api_url, params=params, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        if data['error_code'] != 0:
            raise Exception(data['error_msg'])
        data = data['data']
        total = data['total_search_result_count']
        data = data['results']
        return total, data

    def query(self, query: str, num: int = 50, stemming: int = 0, sort: List[dict] = None,
              collapse_type: str = None, collapse_by: str = None, collapse_order: str = None) -> list[dict]:
        """
        get data from zhihuiya patent query api
        :param query: query string
        :param num: num of data
        :param stemming: 是否开启截词：开启截词，在保留原词的同时，并扩展其对应的单复数及时态
        :param sort: 字段排序, [{"field": "field_name", "order": "asc"}].
            field support: "PBDT_YEARMONTHDAY", "apply_date", "ISD","SCORE".
            order support: "asc", "desc"
        :param collapse_type: 选择专利去重条件, 如：ALL不去重、APNO按申请号去重、DOCDB按简单同族去重、INPADOC按inpadoc同族去重，以及EXTEND按patsnap同族去重，空值默认为ALL
        :param collapse_by: 选择专利去重的排序字段，如：APD按申请日排序、PBD按公开日排序、AUTHORITY按受理局排序，以及SCORE按照查询相关性排序
        :param collapse_order: 选择专利去重的排序顺序，如果collapse_type等于APNO，collapse_by等于APD或PBD，collapse_order的有效值应该为OLDEST或LATEST
        """
        limit = min(num, self.max_limit)
        offset = 0
        query = query.strip()
        total, result = self.query_once(query, limit, offset, stemming, sort, collapse_type, collapse_by, collapse_order)

        rest_num = min(total, num) - limit
        while rest_num > 0:
            limit = min(rest_num, self.max_limit)
            offset = len(result)
            total, data = self.query_once(query, limit, offset, stemming, sort, collapse_type, collapse_by, collapse_order)
            result.extend(data)
            rest_num -= limit
            time.sleep(self.interval)

        return result


class PatentQueryTool(BuiltinTool):
    def _invoke(self,
                user_id: str,
                tool_parameters: dict[str, Any],
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        query = tool_parameters.get('query')
        num = tool_parameters.get('num', 50)
        stemming = tool_parameters.get('stemming', False)
        stemming = 1 if stemming else 0
        sort = tool_parameters.get('sort')
        sort_order = tool_parameters.get('sort_order')
        if sort and sort_order:
            sort = [{"field": sort, "order": sort_order}]
        collapse_type = tool_parameters.get('collapse_type', 'DOCDB')
        collapse_by = tool_parameters.get('collapse_by', 'PBD')
        collapse_order = tool_parameters.get('collapse_order', 'LATEST')

        results = PatentQueryAPI(self.runtime.credentials).query(query, num, stemming, sort, collapse_type, collapse_by, collapse_order)
        return [self.create_json_message(r) for r in results]
