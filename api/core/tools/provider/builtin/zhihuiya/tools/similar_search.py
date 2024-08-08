import json
import time
import requests
from typing import List, Any, Union
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.provider.builtin.zhihuiya.zhihuiya import ZhiHuiYaProvider
from core.tools.tool.builtin_tool import BuiltinTool


class SimilarSearchAPI:
    api_key = ""
    api_url = "https://connect.zhihuiya.com/search/patent/similar-search-patent"
    max_limit = 1000
    max_offset = 20000
    interval = 1

    def __init__(self, credentials: dict):
        self.api_key = credentials["api_key"]
        self.token = ZhiHuiYaProvider().get_bearer_token(credentials)

    def query_once(self, patent_id: str, patent_number: str, limit: int = 50, offset: int = 0, relevancy: str = "50%", country=None):
        """
        get data from zhihuiya similar search api once
        :param patent_id: patent id, 专利Id
        :param patent_number: patent number, 专利公开(公告)号
        :param limit: limit of data
        :param offset: offset of data
        :param relevancy: 最小相似度
        :param country: 允许输入 国家/地区/组织代码及申请类型。 国家/地区/组织代码请参照https://analytics.zhihuiya.com/status，类型请参照A: 发明申请，B: 授权发明，U: 实用新型，D: 外观设计。可以多选，多个内容项之间用英文,隔开。
        """
        if limit <= 0:
            return 0, []

        params = {
            "apikey": self.api_key
        }

        payload = {
            "limit": limit,
            "apd_to": "*",
            "offset": offset,
            "pbd_to": "*",
            "country": country,
            "apd_from": "*",
            "pbd_from": "*",
            "patent_id": patent_id,
            "relevancy": relevancy,
            "patent_number": patent_number
        }

        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer {token}"
        }

        response = requests.request("POST", self.api_key, params=params, json=payload, headers=headers)
        response.raise_for_status()

        data = json.loads(response.text)
        if data['error_code'] != 0:
            raise Exception(data['error_msg'])
        total = data['total_search_result_count']
        data = data['results']
        return total, data

    def search(self, patent_id: str, patent_number: str, num: int = 50, relevancy: str = "50%", country=None):
        """
        get data from zhihuiya similar search api once
        :param patent_id: patent id, 专利Id
        :param patent_number: patent number, 专利公开(公告)号
        :param num: limit of data
        :param relevancy: 最小相似度
        :param country: 允许输入 国家/地区/组织代码及申请类型。 国家/地区/组织代码请参照https://analytics.zhihuiya.com/status，类型请参照A: 发明申请，B: 授权发明，U: 实用新型，D: 外观设计。可以多选，多个内容项之间用英文,隔开。
        """

        if not patent_id and not patent_number:
            raise Exception("patent_id and patent_number can't be both empty")

        limit = min(num, self.max_limit)
        offset = 0
        country = country.strip().split(',')
        total, result = self.query_once(patent_id, patent_number, limit, offset, relevancy, country)

        rest_num = min(total, num) - limit
        while rest_num > 0:
            limit = min(rest_num, self.max_limit)
            offset = len(result)
            total, data = self.query_once(patent_id, patent_number, limit, offset, relevancy, country)
            result.extend(data)
            rest_num -= limit
            time.sleep(self.interval)

        return result


class SimilarSearchTool(BuiltinTool):
    def _invoke(self,
                user_id: str,
                tool_parameters: dict[str, Any],
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        patent_id = tool_parameters.get('patent_id')
        patent_number = tool_parameters.get('patent_number')
        num = tool_parameters.get('num', 50)
        relevancy = tool_parameters.get('relevancy', "50%")
        country = tool_parameters.get('country', 'CNA')
        result = SimilarSearchAPI(self.runtime.credentials).search(patent_id, patent_number, num, relevancy, country)

        return [self.create_json_message(r) for r in result]
