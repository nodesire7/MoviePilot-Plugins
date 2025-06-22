import os
import time
import json
import traceback
from datetime import datetime, timedelta
from typing import Any, List, Dict, Tuple, Optional
from threading import Thread

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.timer import TimerUtils


class QdSignIn(_PluginBase):
    # 插件名称
    plugin_name = "阿飞自用签到助手"
    # 插件描述
    plugin_desc = "支持多个站点的自动签到功能，包括HH、OU、TTG等站点。"
    # 插件图标
    plugin_icon = "QdSignIn.png"
    # 插件版本
    plugin_version = "1.2"
    # 插件作者
    plugin_author = "A-FEI-"
    # 作者主页
    author_url = "https://github.com/nodesire7"
    # 插件配置项ID前缀
    plugin_config_prefix = "qdsignin_"
    # 加载顺序
    plugin_order = 0
    # 可使用的用户级别
    auth_level = 2

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    # 配置属性
    _enabled: bool = False
    _cron: str = ""
    _onlyonce: bool = False
    _notify: bool = False
    _sites: list = []
    _custom_sites: list = []
    _manual_cookies: dict = {}

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        # 停止现有任务
        self.stop_service()

        # 配置
        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._sites = config.get("sites") or []
            self._custom_sites = config.get("custom_sites") or []

            # 处理手动Cookie配置
            self._manual_cookies = {}
            if config.get("hh_cookie"):
                self._manual_cookies["hh"] = config.get("hh_cookie")
            if config.get("ou_cookie"):
                self._manual_cookies["ou"] = config.get("ou_cookie")
            if config.get("ttg_cookie"):
                self._manual_cookies["ttg"] = config.get("ttg_cookie")

            # 保存配置
            self.__update_config()

        # 立即运行一次
        if self._onlyonce:
            # 定时服务
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info("站点签到助手启动，立即运行一次")
            self._scheduler.add_job(func=self.sign_in, trigger='date',
                                    run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                    name="站点签到助手")

            # 关闭一次性开关
            self._onlyonce = False
            # 保存配置
            self.__update_config()

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    def __update_config(self):
        """
        保存配置
        """
        self.update_config(
            {
                "enabled": self._enabled,
                "notify": self._notify,
                "cron": self._cron,
                "onlyonce": self._onlyonce,
                "sites": self._sites,
                "custom_sites": self._custom_sites,
                "hh_cookie": self._manual_cookies.get("hh", ""),
                "ou_cookie": self._manual_cookies.get("ou", ""),
                "ttg_cookie": self._manual_cookies.get("ttg", ""),
            }
        )

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        定义远程控制命令
        """
        return [{
            "cmd": "/qd_signin",
            "event": EventType.PluginAction,
            "desc": "站点签到",
            "category": "站点",
            "data": {
                "action": "qd_signin"
            }
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        """
        return [{
            "path": "/qd_signin",
            "endpoint": self.signin_api,
            "methods": ["GET"],
            "summary": "站点签到",
            "description": "执行站点签到操作",
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        if self._enabled and self._cron:
            try:
                return [{
                    "id": "QdSignIn",
                    "name": "站点签到助手服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.sign_in,
                    "kwargs": {}
                }]
            except Exception as err:
                logger.error(f"定时任务配置错误：{str(err)}")
        elif self._enabled:
            # 随机时间
            triggers = TimerUtils.random_scheduler(num_executions=2,
                                                   begin_hour=9,
                                                   end_hour=23,
                                                   max_interval=6 * 60,
                                                   min_interval=2 * 60)
            ret_jobs = []
            for trigger in triggers:
                ret_jobs.append({
                    "id": f"QdSignIn|{trigger.hour}:{trigger.minute}",
                    "name": "站点签到助手服务",
                    "trigger": "cron",
                    "func": self.sign_in,
                    "kwargs": {
                        "hour": trigger.hour,
                        "minute": trigger.minute
                    }
                })
            return ret_jobs
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 站点选项
        site_options = [
            {"title": "HH (hhanclub.top)", "value": "hh"},
            {"title": "OU (ourbits.club)", "value": "ou"},
            {"title": "TTG (totheglory.im)", "value": "ttg"}
        ]

        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'notify',
                                            'label': '发送通知',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VCronField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '执行周期',
                                            'placeholder': '5位cron表达式，留空自动'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'chips': True,
                                            'multiple': True,
                                            'model': 'sites',
                                            'label': '签到站点',
                                            'items': site_options
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VDivider',
                                        'props': {
                                            'class': 'my-4'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VCardTitle',
                                        'props': {
                                            'class': 'text-h6 mb-2'
                                        },
                                        'content': [
                                            {
                                                'component': 'VIcon',
                                                'props': {
                                                    'class': 'mr-2',
                                                    'icon': 'mdi-cookie'
                                                }
                                            },
                                            '手动Cookie配置'
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'hh_cookie',
                                            'label': 'HH站点Cookie',
                                            'placeholder': 'session_id=abc123;user_id=456',
                                            'variant': 'outlined'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'ou_cookie',
                                            'label': 'OU站点Cookie',
                                            'placeholder': 'session_id=abc123;user_id=456',
                                            'variant': 'outlined'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'ttg_cookie',
                                            'label': 'TTG站点Cookie',
                                            'placeholder': 'session_id=abc123;user_id=456',
                                            'variant': 'outlined'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VCardTitle',
                                        'props': {
                                            'class': 'text-h6 mb-2'
                                        },
                                        'content': [
                                            {
                                                'component': 'VIcon',
                                                'props': {
                                                    'class': 'mr-2',
                                                    'icon': 'mdi-web'
                                                }
                                            },
                                            '自定义站点配置'
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'custom_sites',
                                            'label': '自定义站点配置',
                                            'placeholder': '每行一个站点配置，格式：站点名称|域名|Cookie\n例如：\nHH|https://hhanclub.top/|session_id=abc123;user_id=456\nOU|https://ourbits.club/|auth_token=xyz789;user_name=test',
                                            'rows': 6,
                                            'variant': 'outlined'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': 'Cookie获取优先级：1. MoviePilot站点管理中的Cookie；2. 手动填写的Cookie；3. 自定义站点配置。'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'success',
                                            'variant': 'tonal',
                                            'text': '推荐：在MoviePilot的"站点管理"中配置站点Cookie，插件会自动获取使用。'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'text': '自定义站点配置格式：站点名称|域名|Cookie，每行一个站点。请确保Cookie有效且格式正确。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": True,
            "cron": "",
            "onlyonce": False,
            "sites": [],
            "custom_sites": "",
            "hh_cookie": "",
            "ou_cookie": "",
            "ttg_cookie": ""
        }

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        # 获取签到历史数据
        history_data = self.get_data("signin_history") or {}

        # 构建页面内容
        page_content = [
            {
                'component': 'VCard',
                'props': {
                    'variant': 'flat',
                    'class': 'mb-4'
                },
                'content': [
                    {
                        'component': 'VCardTitle',
                        'props': {
                            'class': 'd-flex align-center'
                        },
                        'content': [
                            {
                                'component': 'VIcon',
                                'props': {
                                    'class': 'mr-2',
                                    'color': 'primary',
                                    'icon': 'mdi-check-circle'
                                }
                            },
                            {
                                'component': 'span',
                                'text': '签到历史记录'
                            }
                        ]
                    },
                    {
                        'component': 'VCardText',
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'info',
                                    'text': '暂无签到记录' if not history_data else f'共有 {len(history_data)} 条签到记录',
                                    'variant': 'tonal'
                                }
                            }
                        ]
                    }
                ]
            }
        ]

        return page_content

    def signin_api(self):
        """
        API接口：执行签到
        """
        try:
            self.sign_in()
            return {"success": True, "message": "签到任务已启动"}
        except Exception as e:
            logger.error(f"API签到失败：{str(e)}")
            return {"success": False, "message": f"签到失败：{str(e)}"}

    def sign_in(self):
        """
        执行签到操作
        """
        # 获取所有需要签到的站点
        all_sites = []

        # 添加预设站点
        if self._sites:
            all_sites.extend(self._sites)

        # 添加自定义站点
        custom_sites = self._parse_custom_sites()
        if custom_sites:
            all_sites.extend([site['name'] for site in custom_sites])

        if not all_sites:
            logger.warning("未配置任何签到站点")
            return

        logger.info("开始执行站点签到...")
        results = {}

        for site in all_sites:
            try:
                logger.info(f"开始签到站点：{site}")
                result = self._signin_site(site)
                results[site] = result

                # 记录签到结果
                self._save_signin_result(site, result)

                # 等待一段时间避免频繁请求
                time.sleep(5)

            except Exception as e:
                error_msg = f"签到失败：{str(e)}"
                logger.error(f"站点 {site} {error_msg}")
                results[site] = {"success": False, "message": error_msg}
                self._save_signin_result(site, {"success": False, "message": error_msg})

        # 发送通知
        if self._notify:
            self._send_notification(results)

        logger.info("站点签到完成")

    def _parse_custom_sites(self) -> list:
        """
        解析自定义站点配置
        """
        custom_sites = []
        if not self._custom_sites:
            return custom_sites

        try:
            lines = self._custom_sites.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split('|')
                if len(parts) >= 3:
                    site_config = {
                        'name': parts[0].strip(),
                        'domain': parts[1].strip(),
                        'cookie': parts[2].strip()
                    }
                    custom_sites.append(site_config)
                    logger.info(f"解析自定义站点配置：{site_config['name']} - {site_config['domain']}")
                else:
                    logger.warning(f"自定义站点配置格式错误：{line}")
        except Exception as e:
            logger.error(f"解析自定义站点配置失败：{str(e)}")

        return custom_sites

    def _get_site_cookie(self, site_name: str, site_domain: str = None) -> str:
        """
        获取站点Cookie，优先使用MP自带站点cookie，其次使用手动填写的cookie
        """
        try:
            # 优先使用MP自带的站点cookie
            from app.db.site_oper import SiteOper

            # 根据站点名称或域名查找站点
            sites = SiteOper().list()
            target_site = None

            for site in sites:
                # 匹配站点名称或域名
                if (site.name and site_name.lower() in site.name.lower()) or \
                   (site.url and site_domain and site_domain in site.url) or \
                   (site.domain and site_domain and site_domain in site.domain):
                    target_site = site
                    break

            if target_site and target_site.cookie:
                logger.info(f"使用MP站点 {target_site.name} 的Cookie")
                return target_site.cookie

            # 如果MP中没有找到，使用手动填写的cookie
            manual_cookie = self._manual_cookies.get(site_name.lower())
            if manual_cookie:
                logger.info(f"使用手动配置的 {site_name} Cookie")
                return manual_cookie

            logger.warning(f"未找到站点 {site_name} 的Cookie配置")
            return ""

        except Exception as e:
            logger.error(f"获取站点Cookie失败：{str(e)}")
            # 降级使用手动填写的cookie
            manual_cookie = self._manual_cookies.get(site_name.lower())
            if manual_cookie:
                logger.info(f"降级使用手动配置的 {site_name} Cookie")
                return manual_cookie
            return ""

    def _signin_site(self, site: str) -> dict:
        """
        执行单个站点签到
        """
        # 检查是否为自定义站点
        custom_sites = self._parse_custom_sites()
        for custom_site in custom_sites:
            if custom_site['name'] == site:
                return self._signin_custom_site(custom_site)

        # 预设站点签到
        if site == "hh":
            return self._signin_hh()
        elif site == "ou":
            return self._signin_ou()
        elif site == "ttg":
            return self._signin_ttg()
        else:
            return {"success": False, "message": f"不支持的站点：{site}"}

    def _signin_custom_site(self, site_config: dict) -> dict:
        """
        执行自定义站点签到
        """
        try:
            from .sites.custom_signin import CustomSignin
            signin_handler = CustomSignin(site_config)
            return signin_handler.signin()
        except Exception as e:
            logger.error(f"自定义站点 {site_config['name']} 签到失败：{str(e)}")
            return {"success": False, "message": f"签到失败：{str(e)}"}

    def _save_signin_result(self, site: str, result: dict):
        """
        保存签到结果
        """
        try:
            history = self.get_data("signin_history") or {}
            today = datetime.now().strftime("%Y-%m-%d")

            if today not in history:
                history[today] = {}

            history[today][site] = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "success": result.get("success", False),
                "message": result.get("message", "")
            }

            # 只保留最近30天的记录
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            history = {k: v for k, v in history.items() if k >= cutoff_date}

            self.save_data("signin_history", history)

        except Exception as e:
            logger.error(f"保存签到结果失败：{str(e)}")

    def _send_notification(self, results: dict):
        """
        发送签到结果通知
        """
        try:
            success_sites = [site for site, result in results.items() if result.get("success")]
            failed_sites = [site for site, result in results.items() if not result.get("success")]

            message = f"站点签到完成\n"
            if success_sites:
                message += f"✅ 成功：{', '.join(success_sites)}\n"
            if failed_sites:
                message += f"❌ 失败：{', '.join(failed_sites)}"

            # 发送系统通知
            self.systemmessage.put(message, title="站点签到助手")

        except Exception as e:
            logger.error(f"发送通知失败：{str(e)}")

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止服务失败：{str(e)}")

    def _signin_hh(self) -> dict:
        """
        HH站点签到
        """
        try:
            cookie = self._get_site_cookie("hh", "hhanclub.top")
            if not cookie:
                return {"success": False, "message": "未找到HH站点Cookie配置"}

            from .sites.hh_signin import HHSignin
            signin_handler = HHSignin(cookie)
            return signin_handler.signin()
        except Exception as e:
            logger.error(f"HH站点签到失败：{str(e)}")
            return {"success": False, "message": "签到失败：" + str(e)}

    def _signin_ou(self) -> dict:
        """
        OU站点签到
        """
        try:
            cookie = self._get_site_cookie("ou", "ourbits.club")
            if not cookie:
                return {"success": False, "message": "未找到OU站点Cookie配置"}

            from .sites.ou_signin import OUSignin
            signin_handler = OUSignin(cookie)
            return signin_handler.signin()
        except Exception as e:
            logger.error(f"OU站点签到失败：{str(e)}")
            return {"success": False, "message": "签到失败：" + str(e)}

    def _signin_ttg(self) -> dict:
        """
        TTG站点签到
        """
        try:
            cookie = self._get_site_cookie("ttg", "totheglory.im")
            if not cookie:
                return {"success": False, "message": "未找到TTG站点Cookie配置"}

            from .sites.ttg_signin import TTGSignin
            signin_handler = TTGSignin(cookie)
            return signin_handler.signin()
        except Exception as e:
            logger.error(f"TTG站点签到失败：{str(e)}")
            return {"success": False, "message": "签到失败：" + str(e)}

    @eventmanager.register(EventType.PluginAction)
    def signin_event(self, event: Event):
        """
        监听插件事件
        """
        if event:
            event_data = event.event_data or {}
            if event_data.get("action") == "qd_signin":
                self.sign_in()