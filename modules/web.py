"""
内置 Web 页面模块

将 HTML 页面嵌入 Python 代码中，通过自定义 URL Scheme 在浏览器内部直接渲染。
使用 WebSocket 向客户端推送数据，客户端主动发起连接请求。

访问地址: delion://zhs.ibin.cc
WS 端点: ws://127.0.0.1:9960/lesson
"""
import asyncio
import secrets
import logging
import json
from typing import Optional, Dict, Any, List, Callable
from PySide6.QtCore import QByteArray, QUrl, QUrlQuery, QBuffer
from PySide6.QtWebEngineCore import QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob

try:
    import websockets
    from websockets.server import serve, WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

_logger = logging.getLogger("WebModule")

# ============================================================
# 配置常量
# ============================================================

CUSTOM_SCHEME = "delion"
APP_DOMAIN = "zhs.ibin.cc"
WS_HOST = "127.0.0.1"
WS_PORT = 9960

# 随机令牌
_access_token: str = secrets.token_urlsafe(32)

# 消息回调函数（用于处理客户端消息）
_on_course_click: Optional[Callable[[str], None]] = None
_on_video_report: Optional[Callable] = None
_on_batch_report: Optional[Callable] = None


def get_access_token() -> str:
    """获取当前访问令牌"""
    return _access_token


def get_app_url(username: str = "用户") -> str:
    """获取应用访问地址"""
    return f"{CUSTOM_SCHEME}://{APP_DOMAIN}?token={_access_token}&username={username}"


def set_course_click_handler(handler: Callable[[str], None]):
    """设置课程点击回调函数"""
    global _on_course_click
    _on_course_click = handler


def set_video_report_handler(handler: Callable):
    """设置视频进度上报回调函数"""
    global _on_video_report
    _on_video_report = handler


def set_batch_report_handler(handler: Callable):
    """设置批量视频上报回调函数"""
    global _on_batch_report
    _on_batch_report = handler


# ============================================================
# HTML 模板
# ============================================================

def get_html_template(username: str = "用户") -> str:
    """生成 HTML 页面，嵌入用户名"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>欢迎页面</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #faf9f5;
            min-height: 100vh;
            overflow: hidden;
        }}
        .welcome-container {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #faf9f5;
            z-index: 100;
            transition: all 1s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .welcome-container.moved {{
            top: 50px;
            height: auto;
            min-height: auto;
            position: absolute;
        }}
        .welcome-text {{
            font-size: 48px;
            font-weight: 600;
            color: #141413;
            opacity: 0;
            transform: scale(0.8);
            animation: welcomeIn 0.8s ease-out forwards;
        }}
        @keyframes welcomeIn {{
            0% {{ opacity: 0; transform: scale(0.8); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
        .content-container {{
            opacity: 0;
            transform: translateY(30px);
            transition: all 0.6s ease-out;
            padding: 20px;
            margin-top: 150px;
            display: flex;
            flex-direction: row;
            justify-content: center;
            align-items: flex-start;
            gap: 30px;
        }}
        .content-container.visible {{
            opacity: 1;
            transform: translateY(0);
        }}
        .info-box {{
            background: #ffffff;
            border-radius: 12px;
            padding: 20px 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            border: 1px solid #e8e6dc;
            width: 48%;
            max-width: 550px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .info-box:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        }}
        .box-title {{
            font-size: 18px;
            font-weight: 600;
            color: #141413;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #d97757;
            text-align: center;
        }}
        .highlight {{
            color: #d97757;
            font-weight: 500;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .info-table th {{
            font-size: 14px;
            font-weight: 500;
            color: #b0aea5;
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #e8e6dc;
        }}
        .info-table td {{
            font-size: 14px;
            font-weight: 500;
            color: #d97757;
            padding: 8px 12px;
            text-align: left;
        }}
        .info-table tr.clickable {{
            cursor: pointer;
            transition: background 0.2s;
        }}
        .info-table tr.clickable:hover {{
            background: #faf9f5;
        }}
        .info-table tr.clickable:active {{
            background: #f0efe8;
        }}
        .info-table tr.selected {{
            background: #fff5f0;
            border-left: 3px solid #d97757;
        }}

        /* 章节折叠样式 */
        .chapter-list {{
            max-height: 300px;
            overflow-y: auto;
        }}
        .chapter-item {{
            margin-bottom: 8px;
        }}
        .chapter-header {{
            background: #f5f4ef;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            font-weight: 500;
            color: #141413;
            transition: background 0.2s;
        }}
        .chapter-header:hover {{
            background: #ebe9e0;
        }}
        .chapter-arrow {{
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #b0aea5;
            transition: transform 0.2s;
        }}
        .chapter-item.expanded .chapter-arrow {{
            transform: rotate(180deg);
        }}
        .chapter-videos {{
            display: none;
            padding-left: 20px;
            margin-top: 4px;
        }}
        .chapter-item.expanded .chapter-videos {{
            display: block;
        }}
        .video-item {{
            padding: 6px 12px;
            font-size: 13px;
            color: #666;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #f0efe8;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .video-item:hover {{
            background: #f5f4ef;
        }}
        .video-item:active {{
            background: #ebe9e0;
        }}
        .video-item:last-child {{
            border-bottom: none;
        }}
        .video-status {{
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 10px;
        }}
        .video-status.done {{
            background: #e8f5e9;
            color: #2e7d32;
        }}
        .video-status.undone {{
            background: #fff3e0;
            color: #ef6c00;
        }}

        /* 复选框样式 */
        .video-checkbox {{
            width: 16px;
            height: 16px;
            accent-color: #d97757;
            cursor: pointer;
            flex-shrink: 0;
            margin-right: 8px;
        }}
        .video-item {{
            display: flex;
            align-items: center;
        }}
        .video-item span:first-of-type {{
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        /* 队列运行中透明全屏覆盖层 */
        .queue-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.85);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }}
        .queue-overlay.visible {{
            display: flex;
        }}
        .queue-overlay-content {{
            background: #fff;
            border-radius: 16px;
            padding: 40px 60px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 400px;
            width: 90%;
        }}
        .queue-overlay-title {{
            font-size: 24px;
            font-weight: 600;
            color: #141413;
            margin-bottom: 24px;
        }}
        .queue-overlay-progress {{
            font-size: 48px;
            font-weight: 700;
            color: #d97757;
            margin-bottom: 16px;
        }}
        .queue-overlay-info {{
            font-size: 16px;
            color: #666;
            margin-bottom: 24px;
        }}
        .queue-overlay-video {{
            font-size: 14px;
            color: #999;
            background: #f5f4ef;
            padding: 12px 16px;
            border-radius: 8px;
            word-break: break-all;
            max-height: 80px;
            overflow-y: auto;
        }}
        .queue-overlay-spinner {{
            width: 60px;
            height: 60px;
            border: 4px solid #f0efe8;
            border-top-color: #d97757;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 24px;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        /* 批量操作按钮 */
        .batch-action-bar {{
            display: flex;
            padding: 8px 12px;
            background: #fff5f0;
            border-top: 2px solid #d97757;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }}
        .batch-action-bar.visible {{
            display: flex;
        }}
        .batch-info {{
            font-size: 13px;
            color: #666;
        }}
        .batch-info .highlight {{
            color: #d97757;
            font-weight: 600;
        }}
        .batch-btn {{
            padding: 6px 16px;
            background: #d97757;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            flex-shrink: 0;
        }}
        .batch-btn:hover {{
            background: #c4623f;
        }}
        .batch-btn:active {{
            transform: scale(0.97);
        }}
        .batch-btn:disabled {{
            background: #b0aea5;
            cursor: not-allowed;
        }}
        .batch-select-all {{
            font-size: 13px;
            color: #d97757;
            cursor: pointer;
            text-decoration: underline;
            white-space: nowrap;
        }}
        .batch-select-all:hover {{
            color: #c4623f;
        }}

        /* WebSocket 状态栏 */
        .ws-status {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            padding: 6px 16px;
            background: #ffffff;
            border-top: 1px solid #e8e6dc;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: #b0aea5;
            z-index: 200;
        }}
        .ws-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #e74c3c;
            transition: background 0.3s;
        }}
        .ws-dot.connected {{
            background: #2ecc71;
        }}
        .ws-dot.connecting {{
            background: #f39c12;
            animation: pulse 1s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
    </style>
</head>
<body>
    <div class="welcome-container" id="welcomeContainer">
        <h1 class="welcome-text">欢迎<span class="highlight">{username}</span>同学</h1>
    </div>
    <div class="content-container" id="contentContainer">
        <div class="info-box">
            <div class="box-title">课程</div>
            <table class="info-table" id="courseTable">
                <thead>
                    <tr>
                        <th>序号</th>
                        <th>课程名称</th>
                        <th>进度</th>
                    </tr>
                </thead>
                <tbody id="courseTableBody">
                    <tr><td colspan="3" style="color:#b0aea5;">加载中...</td></tr>
                </tbody>
            </table>
        </div>
        <div class="info-box">
            <div class="batch-action-bar" id="batchActionBar">
                <span class="batch-select-all" id="batchSelectAll" onclick="toggleSelectAll()">全选未完成</span>
                <span class="batch-info">已选 <span class="highlight" id="selectedCount">0</span> 个视频</span>
                <span class="box-title" style="margin-left:auto;margin-right:auto;">视频信息</span>
                <button class="batch-btn" id="batchStartBtn" onclick="startBatchReport()">开始刷课</button>
            </div>
            <div class="chapter-list" id="chapterList">
                <div style="color:#b0aea5;text-align:center;padding:20px;">请先选择课程</div>
            </div>
        </div>
    </div>

    <!-- WebSocket 状态栏 -->
    <div class="ws-status">
        <div class="ws-dot" id="wsDot"></div>
        <span id="wsText">未连接</span>
    </div>

    <!-- 队列运行中透明全屏覆盖层 -->
    <div class="queue-overlay" id="queueOverlay">
        <div class="queue-overlay-content">
            <div class="queue-overlay-spinner"></div>
            <div class="queue-overlay-title">正在批量刷课</div>
            <div class="queue-overlay-progress" id="queueProgress">0/0</div>
            <div class="queue-overlay-info">请稍候，正在处理队列...</div>
            <div class="queue-overlay-video" id="queueCurrentVideo">-</div>
        </div>
    </div>

    <script>
        // WebSocket 连接
        let ws = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;
        const wsUrl = 'ws://{WS_HOST}:{WS_PORT}/lesson';
        let selectedCourseId = null;
        let isHandshakeDone = false;
        const pageLoadTime = Date.now(); // 页面加载时间戳
        
        // 获取页面URL中的token
        function getPageToken() {{
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('token') || '';
        }}

        function updateStatus(state, text) {{
            const dot = document.getElementById('wsDot');
            const label = document.getElementById('wsText');
            dot.className = 'ws-dot ' + state;
            label.textContent = text;
        }}

        function connectWS() {{
            if (ws) {{
                ws.close();
                ws = null;
            }}

            isHandshakeDone = false;
            updateStatus('connecting', '正在连接...');
            console.log('正在连接 WebSocket:', wsUrl);

            try {{
                ws = new WebSocket(wsUrl);
            }} catch (e) {{
                console.error('WebSocket 创建失败:', e);
                updateStatus('', '连接失败');
                scheduleReconnect();
                return;
            }}

            ws.onopen = function() {{
                console.log('WebSocket 已连接');
                reconnectAttempts = 0;
                updateStatus('connecting', '正在验证...');
                
                // 发送握手消息：时间戳 + token
                const handshakeData = {{
                    command: 'handshake',
                    data: {{
                        timestamp: pageLoadTime,
                        token: getPageToken()
                    }}
                }};
                console.log('发送握手消息:', handshakeData);
                ws.send(JSON.stringify(handshakeData));
            }};

            ws.onmessage = function(event) {{
                console.log('收到消息:', event.data);
                if (!isHandshakeDone) {{
                    // 处理握手响应
                    try {{
                        const msg = JSON.parse(event.data);
                        if (msg.command === 'handshake') {{
                            isHandshakeDone = true;
                            if (msg.data.success) {{
                                updateStatus('connected', '已连接');
                                console.log('握手成功，服务器时间:', msg.data.timestamp);
                                // 握手成功后，请求课程数据
                                sendMessage('request_courses', {{}});
                                // 查询队列状态（页面刷新后恢复覆盖层）
                                sendMessage('query-queue-status', {{}});
                            }} else {{
                                console.error('握手失败:', msg.data.message);
                                updateStatus('', '验证失败');
                                ws.close();
                            }}
                            return;
                        }}
                    }} catch (e) {{
                        console.error('解析握手响应失败:', e);
                    }}
                }}
                // 处理其他消息
                handleMessage(event.data);
            }};

            ws.onclose = function(event) {{
                console.log('WebSocket 已断开, code:', event.code);
                updateStatus('', '已断开');
                ws = null;
                isHandshakeDone = false;
                scheduleReconnect();
            }};

            ws.onerror = function(error) {{
                console.error('WebSocket 错误');
                updateStatus('', '连接错误');
            }};
        }}

        function scheduleReconnect() {{
            reconnectAttempts++;
            if (reconnectAttempts < maxReconnectAttempts) {{
                const delay = Math.min(2000 * reconnectAttempts, 10000);
                updateStatus('connecting', reconnectAttempts + '/' + maxReconnectAttempts + ' 重连中...');
                console.log(delay / 1000 + '秒后重连...');
                setTimeout(connectWS, delay);
            }} else {{
                updateStatus('', '连接失败，停止重连');
                console.error('WebSocket 重连次数过多，停止重连');
            }}
        }}

        function sendMessage(command, data) {{
            if (!ws || ws.readyState !== WebSocket.OPEN) {{
                console.error('WebSocket 未连接');
                return;
            }}
            const msg = JSON.stringify({{command: command, data: data}});
            ws.send(msg);
            console.log('发送消息:', msg);
        }}

        function handleMessage(data) {{
            try {{
                const msg = JSON.parse(data);
                const command = msg.command;
                const payload = msg.data;

                if (command === 'Refresh-课程') {{
                    refreshCourseTable(payload);
                }} else if (command === 'Select-视频') {{
                    refreshVideoTable(payload);
                }} else if (command === 'Update-视频状态') {{
                    updateVideoStatus(payload);
                }} else if (command === 'Batch-队列结束') {{
                    onBatchQueueEnd();
                }} else if (command === 'Queue-状态更新') {{
                    // 队列状态更新：显示/更新覆盖层
                    if (payload.running) {{
                        if (payload.update) {{
                            // 更新进度
                            updateQueueOverlay(payload.total, payload.current, payload.videoName || '处理中...');
                        }} else {{
                            // 首次显示覆盖层
                            showQueueOverlay(payload.total, payload.current, payload.videoName || '处理中...');
                        }}
                    }} else {{
                        // 队列结束，隐藏覆盖层
                        hideQueueOverlay();
                    }}
                }}
            }} catch (e) {{
                console.error('解析消息失败:', e);
            }}
        }}

        function refreshCourseTable(data) {{
            const tbody = document.getElementById('courseTableBody');
            if (!tbody || !Array.isArray(data)) return;

            tbody.innerHTML = data.map((item, index) => `
                <tr class="clickable" data-id="${{item.secret || ''}}" onclick="onCourseClick(this, '${{item.secret || ''}}')">
                    <td>${{index + 1}}</td>
                    <td>${{item.name || item.courseName || '-'}}</td>
                    <td>${{item.progress || '0'}}%</td>
                </tr>
            `).join('');
        }}

        function onCourseClick(row, secret) {{
            // 移除其他选中状态
            document.querySelectorAll('#courseTableBody tr').forEach(r => r.classList.remove('selected'));
            // 添加选中状态
            row.classList.add('selected');
            selectedCourseId = secret;
            console.log('选择课程:', secret);
            // 发送给服务器
            sendMessage('Select-课程', {{secret: secret}});
            // 显示加载中
            document.getElementById('chapterList').innerHTML = '<div style="color:#b0aea5;text-align:center;padding:20px;">加载中...</div>';
        }}

        function refreshVideoTable(chapters) {{
            const container = document.getElementById('chapterList');
            if (!container || !Array.isArray(chapters)) return;

            if (chapters.length === 0) {{
                container.innerHTML = '<div style="color:#b0aea5;text-align:center;padding:20px;">暂无视频</div>';
                return;
            }}

            container.innerHTML = chapters.map((chapter, idx) => {{
                const videos = chapter.videos || [];
                const doneCount = videos.filter(v => v.status === '已完成').length;
                const undoneCount = videos.length - doneCount;
                return `
                <div class="chapter-item" id="chapter-${{idx}}">
                    <div class="chapter-header" onclick="toggleChapter(${{idx}})">
                        <div class="chapter-arrow"></div>
                        <span>${{chapter.name || '未知章节'}}</span>
                        <span style="color:#b0aea5;font-size:12px;margin-left:auto;">已完成${{doneCount}}/未完成${{undoneCount}}</span>
                    </div>
                    <div class="chapter-videos">
                        ${{videos.map((video, vIdx) => `
                            <div class="video-item" id="video-${{video.videoId || vIdx}}" onclick="onVideoClick(${{JSON.stringify(video).replace(/"/g, '&quot;')}})">
                                <input type="checkbox" class="video-checkbox" data-video-id="${{video.videoId || ''}}"
                                    ${{video.status === '已完成' ? 'disabled' : ''}}
                                    onclick="event.stopPropagation(); onCheckboxChange(this, ${{JSON.stringify(video).replace(/"/g, '&quot;')}})">
                                <span>${{video.name || '-'}}</span>
                                <span class="video-status ${{video.status === '已完成' ? 'done' : 'undone'}}">${{video.status || '未完成'}}</span>
                            </div>
                        `).join('')}}
                    </div>
                </div>
            `;}}).join('');
        }}

        function updateVideoStatus(data) {{
            // 部分更新：只更新单个视频的状态
            const videoId = data.videoId;
            const status = data.status || '已完成';
            if (!videoId) return;

            const videoItem = document.getElementById('video-' + videoId);
            if (videoItem) {{
                const statusSpan = videoItem.querySelector('.video-status');
                if (statusSpan) {{
                    statusSpan.textContent = status;
                    statusSpan.className = 'video-status ' + (status === '已完成' ? 'done' : 'undone');
                }}
                // 已完成的视频禁用复选框并取消选中
                if (status === '已完成') {{
                    const checkbox = videoItem.querySelector('.video-checkbox');
                    if (checkbox) {{
                        checkbox.checked = false;
                        checkbox.disabled = true;
                    }}
                    // 从选中列表中移除
                    selectedVideos = selectedVideos.filter(v => String(v.videoId) !== String(videoId));
                    updateBatchBar();
                }}
            }}

            // 更新章节标题中的计数
            updateChapterCounts();
        }}

        function updateChapterCounts() {{
            // 重新计算每个章节的完成/未完成数量
            document.querySelectorAll('.chapter-item').forEach(item => {{
                const videos = item.querySelectorAll('.video-item');
                let doneCount = 0;
                videos.forEach(v => {{
                    const status = v.querySelector('.video-status');
                    if (status && status.textContent === '已完成') doneCount++;
                }});
                const undoneCount = videos.length - doneCount;
                const countSpan = item.querySelector('.chapter-header span:last-child');
                if (countSpan) {{
                    countSpan.textContent = '已完成' + doneCount + '/未完成' + undoneCount;
                }}
            }});
        }}

        function toggleChapter(idx) {{
            const item = document.getElementById('chapter-' + idx);
            if (item) {{
                item.classList.toggle('expanded');
            }}
        }}

        function onVideoClick(video) {{
            if (!ws || ws.readyState !== WebSocket.OPEN) {{
                alert('WebSocket 未连接，请刷新页面');
                return;
            }}
            ws.send(JSON.stringify({{
                command: 'Report-进度',
                data: video
            }}));
        }}

        // 存储选中的视频数据
        let selectedVideos = [];

        function onCheckboxChange(checkbox, video) {{
            if (checkbox.checked) {{
                selectedVideos.push(video);
            }} else {{
                selectedVideos = selectedVideos.filter(v => v.videoId !== video.videoId);
            }}
            updateBatchBar();
        }}

        function updateBatchBar() {{
            const bar = document.getElementById('batchActionBar');
            const count = document.getElementById('selectedCount');
            const btn = document.getElementById('batchStartBtn');
            const selectAll = document.getElementById('batchSelectAll');

            if (selectedVideos.length > 0) {{
                bar.classList.add('visible');
                count.textContent = selectedVideos.length;
                btn.disabled = false;
            }} else {{
                bar.classList.remove('visible');
                count.textContent = '0';
                btn.disabled = true;
            }}
        }}

        function toggleSelectAll() {{
            const checkboxes = document.querySelectorAll('.video-checkbox:not(:disabled)');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);

            if (allChecked) {{
                // 取消全选
                checkboxes.forEach(cb => {{
                    cb.checked = false;
                }});
                selectedVideos = [];
            }} else {{
                // 全选未完成的
                selectedVideos = [];
                checkboxes.forEach(cb => {{
                    cb.checked = true;
                    const videoData = getVideoDataFromCheckbox(cb);
                    if (videoData) selectedVideos.push(videoData);
                }});
            }}
            updateBatchBar();
        }}

        function getVideoDataFromCheckbox(checkbox) {{
            // 从视频元素的 onclick 属性中提取视频数据
            const videoItem = checkbox.closest('.video-item');
            if (!videoItem) return null;
            const onclickStr = videoItem.getAttribute('onclick');
            if (!onclickStr) return null;
            try {{
                const match = onclickStr.match(/onVideoClick\\((\\{{[\\s\\S]*?\\}})\\)/);
                if (match) return JSON.parse(match[1]);
            }} catch(e) {{}}
            return null;
        }}

        function startBatchReport() {{
            if (selectedVideos.length === 0) {{
                alert('请先选择要刷课的视频');
                return;
            }}
            if (!ws || ws.readyState !== WebSocket.OPEN) {{
                alert('WebSocket 未连接，请刷新页面');
                return;
            }}

            // 过滤掉已完成的视频
            const undoneVideos = selectedVideos.filter(v => v.status !== '已完成');
            if (undoneVideos.length === 0) {{
                alert('所选视频均已完成');
                return;
            }}

            // 禁用按钮防止重复点击
            const btn = document.getElementById('batchStartBtn');
            btn.disabled = true;
            btn.textContent = '队列处理中...';

            // 发送批量上报请求
            sendMessage('Batch-Report-进度', {{ videos: undoneVideos }});
        }}

        function onBatchQueueEnd() {{
            // 队列处理结束，重置按钮和选择状态
            const btn = document.getElementById('batchStartBtn');
            btn.disabled = false;
            btn.textContent = '开始刷课';
            // 清空选择
            selectedVideos = [];
            document.querySelectorAll('.video-checkbox').forEach(cb => cb.checked = false);
            updateBatchBar();
            // 隐藏覆盖层
            hideQueueOverlay();
        }}

        // 显示队列覆盖层
        function showQueueOverlay(total, current, videoName) {{
            const overlay = document.getElementById('queueOverlay');
            const progress = document.getElementById('queueProgress');
            const videoDiv = document.getElementById('queueCurrentVideo');

            progress.textContent = `${{current}}/${{total}}`;
            videoDiv.textContent = videoName || '准备中...';
            // 只有未显示时才添加 class，避免重复触发 transition
            if (!overlay.classList.contains('visible')) {{
                overlay.classList.add('visible');
            }}
        }}

        // 更新队列覆盖层进度
        function updateQueueOverlay(total, current, videoName) {{
            const progress = document.getElementById('queueProgress');
            const videoDiv = document.getElementById('queueCurrentVideo');

            progress.textContent = `${{current}}/${{total}}`;
            videoDiv.textContent = videoName || '处理中...';
        }}

        // 隐藏队列覆盖层
        function hideQueueOverlay() {{
            const overlay = document.getElementById('queueOverlay');
            overlay.classList.remove('visible');
        }}

        // 页面加载
        window.addEventListener('load', function() {{
            const welcomeContainer = document.getElementById('welcomeContainer');
            const contentContainer = document.getElementById('contentContainer');

            // 连接 WebSocket
            connectWS();

            // 4秒后执行动画
            setTimeout(function() {{
                welcomeContainer.classList.add('moved');
                setTimeout(function() {{
                    contentContainer.classList.add('visible');
                }}, 300);
            }}, 4000);
        }});

        // 页面关闭时断开连接
        window.addEventListener('beforeunload', function() {{
            if (ws) ws.close();
        }});
    </script>
</body>
</html>"""


# ============================================================
# WebSocket 服务器
# ============================================================

_ws_server = None
_ws_started = False
_ws_clients: List[WebSocketServerProtocol] = []
# 记录每个客户端的握手状态
_client_handshake_status: dict = {}
# 缓存课程数据
_cached_courses: list = []
# 请求课程数据的回调
_on_request_courses: Optional[Callable] = None


async def _ws_handler(websocket):
    """处理 WebSocket 连接"""
    _ws_clients.append(websocket)
    _logger.info(f"WS 客户端已连接，当前连接数: {len(_ws_clients)}")
    
    is_handshake_done = False

    try:
        # 持续接收客户端消息
        async for message in websocket:
            _logger.info(f"收到客户端消息: {message}")
            try:
                msg = json.loads(message)
                command = msg.get('command')
                data = msg.get('data', {})
                
                # 处理握手消息
                if command == 'handshake' and not is_handshake_done:
                    client_timestamp = data.get('timestamp')
                    client_token = data.get('token')
                    
                    # 验证 token
                    token_valid = (client_token == _access_token)
                    
                    # 构造握手响应
                    handshake_response = json.dumps({
                        "command": "handshake",
                        "data": {
                            "timestamp": client_timestamp,
                            "success": token_valid,
                            "message": "验证成功" if token_valid else "Token 验证失败"
                        }
                    })
                    
                    await websocket.send(handshake_response)
                    _logger.info(f"握手响应已发送: {'成功' if token_valid else '失败'}")
                    
                    if not token_valid:
                        # Token 验证失败，关闭连接
                        await websocket.close(code=1008, reason="Token 验证失败")
                        return
                    
                    is_handshake_done = True
                    _client_handshake_status[websocket.id if hasattr(websocket, 'id') else id(websocket)] = True
                    continue
                
                # 握手完成后才处理其他消息
                if not is_handshake_done:
                    _logger.warning("收到未握手前的消息，忽略")
                    continue
                
                # 处理课程选择消息
                if command == 'Select-课程' and _on_course_click:
                    secret = data.get('secret')
                    if secret:
                        # 在后台线程中执行回调（避免阻塞 WS 循环）
                        asyncio.create_task(_handle_course_click(secret))
                
                # 处理视频进度上报消息
                elif command == 'Report-进度' and _on_video_report:
                    asyncio.create_task(_handle_video_report(data))

                # 处理批量视频进度上报消息
                elif command == 'Batch-Report-进度' and _on_batch_report:
                    asyncio.create_task(_handle_batch_report(data))
                
                # 处理请求课程数据
                elif command == 'request_courses':
                    # 先发送缓存的数据
                    if _cached_courses:
                        await send_ws_message("Refresh-课程", _cached_courses)
                    # 调用回调获取最新数据
                    if _on_request_courses:
                        asyncio.create_task(_on_request_courses())

                # 处理查询队列状态（页面刷新后恢复）
                elif command == 'query-queue-status':
                    from modules.Line_up import get_queue_status
                    status = get_queue_status()
                    await send_ws_message("Queue-状态更新", {
                        "running": status["is_running"],
                        "total": status["total"],
                        "current": status["current_index"] + 1 if status["is_running"] else 0,
                        "videoName": ""
                    })
            except json.JSONDecodeError:
                _logger.warning(f"收到无效的 JSON 消息: {message}")
            except Exception as e:
                _logger.error(f"处理消息失败: {e}")
    except Exception as e:
        _logger.debug(f"WS 连接异常: {e}")
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
        # 清理握手状态
        ws_key = websocket.id if hasattr(websocket, 'id') else id(websocket)
        if ws_key in _client_handshake_status:
            del _client_handshake_status[ws_key]
        _logger.info(f"WS 客户端已断开，当前连接数: {len(_ws_clients)}")


async def _handle_course_click(secret: str):
    """处理课程点击事件"""
    if _on_course_click:
        try:
            # 如果回调是协程函数，await 它
            if asyncio.iscoroutinefunction(_on_course_click):
                await _on_course_click(secret)
            else:
                _on_course_click(secret)
        except Exception as e:
            _logger.error(f"处理课程点击失败: {e}")


async def _handle_video_report(data: dict):
    """处理视频进度上报事件"""
    if _on_video_report:
        try:
            if asyncio.iscoroutinefunction(_on_video_report):
                await _on_video_report(data)
            else:
                _on_video_report(data)
        except Exception as e:
            _logger.error(f"处理视频上报失败: {e}")


async def _handle_batch_report(data: dict):
    """处理批量视频进度上报事件"""
    if _on_batch_report:
        try:
            if asyncio.iscoroutinefunction(_on_batch_report):
                await _on_batch_report(data)
            else:
                _on_batch_report(data)
        except Exception as e:
            _logger.error(f"处理批量上报失败: {e}")


async def start_ws_server():
    """启动 WebSocket 服务器"""
    global _ws_server, _ws_started

    if _ws_started:
        _logger.info("WS 服务器已在运行中")
        return True

    if not WEBSOCKETS_AVAILABLE:
        _logger.error("websockets 未安装，无法启动 WS 服务器")
        return False

    try:
        _ws_server = await serve(_ws_handler, WS_HOST, WS_PORT)
        _ws_started = True
        _logger.info(f"WS 服务器已启动: ws://{WS_HOST}:{WS_PORT}/lesson")
        return True
    except Exception as e:
        _logger.error(f"WS 服务器启动失败: {e}")
        return False


def is_ws_server_running() -> bool:
    """检查 WS 服务器是否已启动"""
    return _ws_started


async def stop_ws_server():
    """停止 WebSocket 服务器"""
    global _ws_server, _ws_started

    # 先关闭所有客户端连接
    for client in _ws_clients[:]:
        try:
            await client.close(1001, "服务器关闭")
        except Exception:
            pass
    _ws_clients.clear()

    if _ws_server:
        _ws_server.close()
        await _ws_server.wait_closed()
        _ws_server = None
        _ws_started = False
        _logger.info("WS 服务器已停止")


async def send_ws_message(command: str, data: Any):
    """向所有已连接的客户端发送 WebSocket 消息

    Args:
        command: 命令，如 "Refresh-课程"
        data: 数据对象（将被 JSON 序列化）
    """
    global _cached_courses
    
    # 如果是课程数据，则缓存起来
    if command == "Refresh-课程" and isinstance(data, list):
        _cached_courses = data
        _logger.info(f"已缓存 {len(data)} 门课程数据")
    
    if not _ws_clients:
        _logger.warning("没有 WS 客户端连接")
        return

    message = json.dumps({
        "command": command,
        "data": data
    }, ensure_ascii=False)

    # 过滤已关闭的连接
    alive = [c for c in _ws_clients if c.open]
    removed = len(_ws_clients) - len(alive)
    if removed > 0:
        _logger.info(f"清理了 {removed} 个已断开的 WS 连接")
        _ws_clients.clear()
        _ws_clients.extend(alive)

    if not alive:
        _logger.warning("没有活跃的 WS 客户端连接")
        return

    for client in alive:
        try:
            await client.send(message)
        except Exception as e:
            _logger.warning(f"发送 WS 消息失败: {e}")
            if client in _ws_clients:
                _ws_clients.remove(client)


def set_request_courses_handler(handler: Optional[Callable]):
    """设置请求课程数据的回调函数"""
    global _on_request_courses
    _on_request_courses = handler


# ============================================================
# URL Scheme Handler
# ============================================================

class AppUrlSchemeHandler(QWebEngineUrlSchemeHandler):
    """自定义 URL Scheme 处理器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffers = []

    def requestStarted(self, request: QWebEngineUrlRequestJob):
        """处理请求"""
        url = request.requestUrl()
        host = url.host()

        # 验证域名
        if host != APP_DOMAIN:
            self._send_response(request, b"<html><body><h1>403 Forbidden</h1></body></html>", b"text/html")
            return

        # 验证令牌
        query = QUrlQuery(url)
        token = query.queryItemValue("token")
        if token != _access_token:
            self._send_response(request, b"<html><body><h1>403 Forbidden</h1></body></html>", b"text/html")
            return

        # 获取用户名
        username = query.queryItemValue("username") or "用户"

        # 返回 HTML
        html = get_html_template(username)
        self._send_response(request, html.encode('utf-8'), b"text/html; charset=utf-8")
        _logger.info(f"已返回 HTML 页面，用户名: {username}")

    def _send_response(self, request: QWebEngineUrlRequestJob, data: bytes, content_type: bytes):
        """发送响应"""
        buffer = QBuffer()
        buffer.setData(data)
        buffer.open(QBuffer.OpenModeFlag.ReadOnly)
        self._buffers.append(buffer)
        request.reply(content_type, buffer)


# ============================================================
# Scheme 注册
# ============================================================

_scheme_registered = False


def register_custom_scheme():
    """注册自定义 URL Scheme（必须在 QApplication 创建前调用）"""
    global _scheme_registered
    if _scheme_registered:
        return

    from PySide6.QtWebEngineCore import QWebEngineUrlScheme

    scheme = QWebEngineUrlScheme(CUSTOM_SCHEME.encode())
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.LocalScheme |
        QWebEngineUrlScheme.Flag.LocalAccessAllowed |
        QWebEngineUrlScheme.Flag.CorsEnabled |
        QWebEngineUrlScheme.Flag.SecureScheme
    )
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setDefaultPort(0)

    QWebEngineUrlScheme.registerScheme(scheme)
    _scheme_registered = True
    _logger.info(f"已注册自定义 URL Scheme: {CUSTOM_SCHEME}")
