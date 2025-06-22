# 站点签到助手安装指南

## 快速安装

### 1. 准备Cookie文件

在插件目录下创建以下Cookie文件：

- `hhck.json` - HH站点的Cookie（原始cookie字符串格式）
- `ouck.json` - OU站点的Cookie（原始cookie字符串格式）
- `ttgck.json` - TTG站点的Cookie（原始cookie字符串格式）

Cookie格式示例：
```
session_id=abc123; user_id=456; auth_token=xyz789
```

### 2. HH站点特殊配置

对于HH站点，还需要准备：
- `red_dot_template.png` - 签到按钮的模板图片

### 3. 安装依赖

插件会自动安装以下依赖：
- selenium>=4.0.0
- webdriver-manager>=3.8.0
- opencv-python-headless>=4.5.0
- pyautogui>=0.9.50
- numpy>=1.20.0

### 4. 配置插件

1. 在MoviePilot管理界面中找到"站点签到助手"插件
2. 启用插件
3. 选择需要签到的站点
4. 设置执行周期（可选，留空则随机执行）
5. 开启通知（可选）

### 5. 测试运行

点击"立即运行一次"测试插件是否正常工作。

## 故障排除

### Cookie获取方法

1. 登录对应站点
2. 打开浏览器开发者工具（F12）
3. 切换到Network标签
4. 刷新页面
5. 找到主页面请求，查看Request Headers中的Cookie
6. 复制Cookie值到对应的文件中

### 常见问题

1. **ChromeDriver错误**: 确保网络连接正常，插件会自动下载ChromeDriver
2. **签到失败**: 检查Cookie是否有效，站点是否可正常访问
3. **视觉识别失败**: 确保HH站点的模板图片准确

## 注意事项

- 定期更新Cookie文件
- 确保系统已安装Chrome浏览器
- 插件运行时会占用一定系统资源
- 遵守站点使用条款，合理使用自动化功能
