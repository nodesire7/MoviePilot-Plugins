import os
import cv2
import numpy as np
import pyautogui
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager

from app.log import logger


class HHSignin:
    """
    HH站点签到类
    """

    def __init__(self, cookie_string: str = ""):
        self.site_name = "HH"
        self.site_url = "https://hhanclub.top/"
        self.cookie_string = cookie_string
        
    def setup_driver(self):
        """设置Chrome驱动"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--force-device-scale-factor=1")
        chrome_options.add_argument("--window-size=1200,800")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--log-level=3")
        
        try:
            logger.info("正在初始化ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("ChromeDriver初始化成功！")
            return driver
        except Exception as e:
            logger.error(f"初始化驱动失败: {str(e)}")
            raise

    def visual_verification(self, template_path, threshold=0.6, retries=5):
        """视觉检测验证组件并返回坐标"""
        if not os.path.exists(template_path):
            logger.warning(f"模板图片未找到：{template_path}")
            return None
        
        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            logger.warning(f"无法加载模板图片：{template_path}")
            return None
        
        h, w = template.shape

        for _ in range(retries):
            try:
                screenshot = pyautogui.screenshot()
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
                
                res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                
                logger.debug(f"匹配结果：max_val={max_val:.4f}, 阈值={threshold}")
                if max_val >= threshold:
                    center_x = max_loc[0] + w // 2
                    center_y = max_loc[1] + h // 2
                    return (center_x, center_y)
                
                time.sleep(1)
            except Exception as e:
                logger.warning(f"视觉检测失败：{str(e)}")
                
        return None

    def signin(self) -> dict:
        """
        执行HH站点签到
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            driver = None
            try:
                driver = self.setup_driver()
                wait = WebDriverWait(driver, 15)

                # 访问目标网站
                driver.get(self.site_url)
                logger.info("已访问HH站点")

                # 加载Cookie
                if not self.cookie_string:
                    logger.error("Cookie字符串为空")
                    return {"success": False, "message": "Cookie字符串为空"}

                cookies = dict(item.strip().split("=", 1) for item in self.cookie_string.split(";") if "=" in item)

                driver.delete_all_cookies()
                for name, value in cookies.items():
                    driver.add_cookie({"name": name, "value": value})
                driver.refresh()
                logger.info("Cookie已加载并刷新页面")

                # 点击用户头像
                user_avatar = wait.until(EC.element_to_be_clickable((By.ID, "user-avatar")))
                user_avatar.click()
                logger.info("用户信息面板已展开")

                # 点击签到链接
                sign_in_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'attendance.php')]")))
                sign_in_link.click()
                logger.info("已点击签到链接")

                # 等待页面加载
                time.sleep(20)

                # 使用视觉检测找到红点位置并点击
                template_path = os.path.join(os.path.dirname(__file__), "..", "red_dot_template.png")
                red_dot_pos = self.visual_verification(template_path, threshold=0.6, retries=5)
                
                if red_dot_pos:
                    window_position = driver.get_window_position()
                    x_offset, y_offset = window_position['x'], window_position['y']
                    
                    target_x = red_dot_pos[0] - x_offset
                    target_y = red_dot_pos[1] - y_offset
                    
                    pyautogui.moveTo(target_x, target_y, duration=0.5)
                    pyautogui.click()
                    logger.info(f"已点击指定像素坐标 ({target_x}, {target_y})")
                    
                    time.sleep(3)
                    
                    # 保存截图
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    screenshot_path = os.path.join(os.path.dirname(__file__), "..", f"hh_result_{timestamp}.png")
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"已保存操作结果截图: {screenshot_path}")
                    
                    return {"success": True, "message": "签到成功"}
                else:
                    logger.warning("未能找到红点位置")
                    return {"success": False, "message": "未能找到签到按钮"}

            except Exception as e:
                logger.error(f"HH站点签到出现错误：{str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    return {"success": False, "message": f"签到失败，已重试{max_retries}次：{str(e)}"}
                
                logger.info(f"等待{5 * retry_count}秒后第{retry_count}次重试...")
                time.sleep(5 * retry_count)
                
            finally:
                if driver:
                    driver.quit()

        return {"success": False, "message": "签到失败，已达到最大重试次数"}
