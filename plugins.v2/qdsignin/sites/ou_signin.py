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


class OUSignin:
    """
    OU站点签到类
    """

    def __init__(self, cookie_string: str = ""):
        self.site_name = "OU"
        self.site_url = "https://ourbits.club/index.php"
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
            driver.add_cookie(cookie)

        return True

    def save_cookies(self, driver, cookie_file_path):
        """保存Cookie文件"""
        cookies = driver.get_cookies()
        with open(cookie_file_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4)

    def signin(self) -> dict:
        """
        执行OU站点签到
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            driver = None
            try:
                driver = self.setup_driver()

                # 访问目标网站的首页
                driver.get(self.site_url)
                logger.info("已访问OU站点首页")

                # 加载Cookie
                if not self.cookie_string:
                    logger.error("Cookie字符串为空")
                    return {"success": False, "message": "Cookie字符串为空"}

                if self.load_cookies(driver):
                    driver.refresh()
                    logger.info("已加载Cookie并刷新页面")
                else:
                    return {"success": False, "message": "Cookie加载失败"}

                # 点击签到链接
                wait = WebDriverWait(driver, 10)
                try:
                    # 查找签到链接
                    sign_link = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//a[@href='attendance.php' and contains(@class, 'faqlink')]"))
                    )
                    logger.info("找到签到链接，正在点击...")
                    sign_link.click()
                    time.sleep(3)
                    logger.info("已点击签到链接")
                except Exception as e:
                    logger.error(f"未能找到签到链接：{str(e)}")
                    return {"success": False, "message": f"未能找到签到链接：{str(e)}"}

                # 等待签到成功
                total_wait_time = 180
                scroll_interval = 2
                scroll_step = 100

                logger.info(f"开始等待{total_wait_time}秒，期间每隔{scroll_interval}秒滚动一次页面...")
                for elapsed_time in range(0, total_wait_time, scroll_interval):
                    # 滚动页面
                    driver.execute_script(f"window.scrollBy(0, {scroll_step});")
                    logger.debug(f"已等待{elapsed_time}秒，页面已滚动")

                    # 检测是否出现签到成功的提示
                    try:
                        success_message = driver.find_element(By.XPATH, "//h2[@align='left' and contains(text(), '签到成功')]")
                        if success_message.is_displayed():
                            logger.info("OU站点签到成功！")
                            return {"success": True, "message": "签到成功"}
                    except Exception:
                        pass

                    # 等待指定的时间间隔
                    time.sleep(scroll_interval)

                logger.warning("等待时间结束，未检测到签到成功的提示")
                return {"success": False, "message": "签到超时，未检测到成功提示"}

            except Exception as e:
                logger.error(f"OU站点签到出现错误：{str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    return {"success": False, "message": f"签到失败，已重试{max_retries}次：{str(e)}"}

                logger.info(f"等待{5 * retry_count}秒后第{retry_count}次重试...")
                time.sleep(5 * retry_count)

            finally:
                if driver:
                    driver.quit()

        return {"success": False, "message": "签到失败，已达到最大重试次数"}
