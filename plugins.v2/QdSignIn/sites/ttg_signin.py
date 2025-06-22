import time
import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from app.log import logger


class TTGSignin:
    """
    TTG站点签到类
    """

    def __init__(self, cookie_string: str = ""):
        self.site_name = "TTG"
        self.site_url = "https://totheglory.im/"
        self.cookie_string = cookie_string
        
    def setup_driver(self):
        """设置Chrome驱动"""
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        try:
            logger.info("正在初始化ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("ChromeDriver初始化成功！")
            return driver
        except Exception as e:
            logger.error(f"初始化驱动失败: {str(e)}")
            raise

    def parse_cookie_string(self, cookie_string):
        """解析原始Cookie字符串"""
        cookies = []
        for item in cookie_string.split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookies.append({"name": key, "value": value})
        return cookies

    def load_cookies(self, driver):
        """加载Cookie"""
        if not self.cookie_string:
            logger.error("Cookie字符串为空")
            return False

        # 解析原始Cookie字符串
        cookies = self.parse_cookie_string(self.cookie_string)

        # 添加Cookie到浏览器
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.warning(f"添加Cookie失败：{cookie['name']} - {str(e)}")

        return True

    def signin(self) -> dict:
        """
        执行TTG站点签到
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            driver = None
            try:
                driver = self.setup_driver()

                # 访问目标网站的首页
                driver.get(self.site_url)
                logger.info("已访问TTG站点首页")

                # 加载Cookie
                if not self.cookie_string:
                    logger.error("Cookie字符串为空")
                    return {"success": False, "message": "Cookie字符串为空"}

                if self.load_cookies(driver):
                    driver.refresh()
                    logger.info("已加载Cookie并刷新页面")
                else:
                    return {"success": False, "message": "Cookie加载失败"}

                # 等待页面加载
                time.sleep(5)

                # 检查是否已经登录
                if "login.php" in driver.current_url or "登录" in driver.page_source:
                    logger.error("Cookie已失效，需要重新登录")
                    return {"success": False, "message": "Cookie已失效，需要重新登录"}

                # 查找签到相关元素
                wait = WebDriverWait(driver, 15)
                
                # 尝试多种方式查找签到按钮或链接
                signin_selectors = [
                    "//a[contains(@href, 'signed.php')]",
                    "//a[contains(text(), '签到')]",
                    "//input[@type='submit' and contains(@value, '签到')]",
                    "//button[contains(text(), '签到')]"
                ]
                
                signin_element = None
                for selector in signin_selectors:
                    try:
                        signin_element = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        logger.info(f"找到签到元素：{selector}")
                        break
                    except Exception:
                        continue
                
                if signin_element:
                    signin_element.click()
                    logger.info("已点击签到按钮")
                    
                    # 等待签到结果
                    time.sleep(5)
                    
                    # 检查签到结果
                    page_source = driver.page_source
                    if "签到成功" in page_source or "已签到" in page_source:
                        logger.info("TTG站点签到成功！")
                        return {"success": True, "message": "签到成功"}
                    elif "今日已签到" in page_source or "已经签到" in page_source:
                        logger.info("TTG站点今日已签到")
                        return {"success": True, "message": "今日已签到"}
                    else:
                        logger.warning("签到状态未知")
                        return {"success": False, "message": "签到状态未知"}
                else:
                    logger.warning("未找到签到按钮")
                    # 检查是否已经签到
                    page_source = driver.page_source
                    if "今日已签到" in page_source or "已经签到" in page_source:
                        logger.info("TTG站点今日已签到")
                        return {"success": True, "message": "今日已签到"}
                    else:
                        return {"success": False, "message": "未找到签到按钮"}

            except Exception as e:
                logger.error(f"TTG站点签到出现错误：{str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    return {"success": False, "message": f"签到失败，已重试{max_retries}次：{str(e)}"}

                logger.info(f"等待{5 * retry_count}秒后第{retry_count}次重试...")
                time.sleep(5 * retry_count)

            finally:
                if driver:
                    driver.quit()

        return {"success": False, "message": "签到失败，已达到最大重试次数"}
