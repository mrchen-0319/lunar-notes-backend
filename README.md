# 农历记事本 · 后台推送服务（Web Push 后端）

本目录 `backend-dist/` 是 iOS / 任意浏览器 PWA 实现"**关掉软件也推送提醒**"所需的后端。
CloudStudio 仅支持静态托管、跑不了后端，因此本服务需部署到支持 Python 的公网 HTTPS 环境。

## 包含文件
- `server.py`：Flask 服务，托管同一套 PWA 静态文件 + 笔记 API + Web Push 订阅/推送
- `core.py`：与 EXE 共用的农历换算与提醒逻辑
- `index.html` / `lunar.js` / `sw.js` / `manifest.webmanifest` / 图标：PWA 前端
- `requirements.txt`：依赖
- `Procfile` / `render.yaml`：一键部署配置

## 一键部署到 Render
1. 打开 https://render.com ，New → Web Service，连接 Git 仓库（或直接上传本目录）。
2. Render 会自动识别 `render.yaml`：
   - Runtime: Python
   - Build: `pip install -r requirements.txt`
   - Start: `python server.py`
3. 在 Environment 中设置 `VAPID_EMAIL`（推送联系邮箱，如 `mailto:you@example.com`）。`PORT` 由 Render 自动注入。
4. 部署完成后得到 `https://<你的服务>.onrender.com`。

## 一键部署到 Railway
1. 打开 https://railway.app ，New Project → Deploy from GitHub / 本地上传。
2. Railway 读取 `Procfile`：`web: python server.py`，自动安装依赖、注入 `PORT`。
3. 在 Variables 设置 `VAPID_EMAIL`。
4. 部署完成后得到公网 HTTPS 域名。

## 部署后如何启用 iOS 后台推送
1. iPhone 用 **Safari** 打开你的后端地址（必须 https）。
2. 点"分享" → "添加到主屏幕"，安装为 PWA。
3. 从主屏幕打开该 PWA，点界面上的"**开启通知**"，授权订阅。
4. 之后即使 PWA 关闭，到点也会收到系统级推送（后端每 15 分钟检查并推送）。

## 说明
- 笔记通过 `/api/notes` 存于服务端 `notes.json`（与 EXE 同格式），可跨设备同步。
- VAPID 密钥首次启动自动生成并缓存到 `vapid.json`。
- 提醒逻辑与 EXE 完全一致：按农历日期每年触发一次，支持提前 1/3/7 天 + 指定时间。
