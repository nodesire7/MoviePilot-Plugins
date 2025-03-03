import re
from typing import Tuple
from urllib.parse import urljoin

from ruamel.yaml import CommentedMap

from app.core.config import settings
from app.log import logger
from app.plugins.autosignin.sites import _ISiteSigninHandler
from app.utils.http import RequestUtils
from app.utils.string import StringUtils


class HH(_ISiteSigninHandler):
    """
    HH站点签到
    """
    # 站点URL
    site_url = "hhanclub.top"
    base_url = f"https://{site_url}"
    
    # 签到相关URL
    _sign_url = urljoin(base_url, "attendance.php")
    _index_url = base_url
    
    # 签到状态匹配
    _sign_regex = ['今天已经签到过了']
    _sign_text = '今天已经签到过了'
    _success_text = '签到成功'

    def signin(self, site_info: CommentedMap) -> Tuple[bool, str]:
        """
        执行签到操作
        """
        site = site_info.get("name")
        site_cookie = site_info.get("cookie")
        ua = site_info.get("ua")
        proxy = site_info.get("proxy")
        render = site_info.get("render")

        # 设置通用请求头
        headers = {
            "User-Agent": ua or settings.USER_AGENT,
            "Cookie": site_cookie,
            "Referer": self._index_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "X-Requested-With": "XMLHttpRequest"
        }

        try:
            # 1. 访问主页
            index_res = RequestUtils(cookies=site_cookie,
                                   headers=headers,
                                   proxies=settings.PROXY if proxy else None
                                   ).get_res(url=self._index_url)
            
            if not index_res or index_res.status_code != 200:
                logger.error(f"{site} 访问主页失败")
                return False, "访问主页失败"

            if "login.php" in index_res.text:
                logger.error(f"{site} 签到失败，Cookie已失效")
                return False, "Cookie已失效"

            # 2. 模拟点击用户头像
            avatar_url = f"{self._index_url}/usercp.php"
            avatar_res = RequestUtils(cookies=site_cookie,
                                    headers=headers,
                                    proxies=settings.PROXY if proxy else None
                                    ).get_res(url=avatar_url)

            if not avatar_res or avatar_res.status_code != 200:
                logger.error(f"{site} 访问用户面板失败")
                return False, "访问用户面板失败"

            # 3. 访问签到页面
            sign_headers = headers.copy()
            sign_headers["Referer"] = avatar_url
            
            sign_res = RequestUtils(cookies=site_cookie,
                                  headers=sign_headers,
                                  proxies=settings.PROXY if proxy else None
                                  ).get_res(url=self._sign_url)

            if not sign_res or sign_res.status_code != 200:
                logger.error(f"{site} 签到失败，签到请求失败")
                return False, "签到请求失败"

            sign_res.encoding = "utf-8"
            
            # 4. 检查签到结果
            if self._success_text in sign_res.text:
                logger.info(f"{site} 签到成功")
                return True, "签到成功"
            if self._sign_text in sign_res.text or any(regex in sign_res.text for regex in self._sign_regex):
                logger.info(f"{site} 今日已签到")
                return True, "今日已签到"

            # 尝试解析错误信息
            error_match = re.search(r'<div class="error">(.*?)</div>', sign_res.text)
            if error_match:
                error_msg = error_match.group(1).strip()
                logger.error(f"{site} 签到失败：{error_msg}")
                return False, f"签到失败：{error_msg}"

            logger.error(f"{site} 签到失败，未知原因")
            return False, "签到失败，未知原因"

        except Exception as e:
            logger.error(f"{site} 签到异常：{str(e)}")
            return False, f"签到异常：{str(e)}"

    @classmethod
    def match(cls, url: str) -> bool:
        """
        根据站点Url判断是否匹配
        """
        return True if StringUtils.url_equal(url, cls.site_url) else False
