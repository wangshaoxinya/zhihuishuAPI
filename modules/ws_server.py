"""
WebSocket服务器模块 - 用于向本地HTML页面传递数据
"""
import asyncio
import websockets
import json
from typing import Optional, Callable


class WebSocketServer:
    """WebSocket服务器类"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.server = None
        self.clients = set()
        self.message_handler: Optional[Callable] = None
        
    async def start(self):
        """启动WebSocket服务器"""
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        print(f"WebSocket服务器已启动: ws://{self.host}:{self.port}")
        
    async def stop(self):
        """停止WebSocket服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("WebSocket服务器已停止")
            
    async def _handle_client(self, websocket, path):
        """处理客户端连接"""
        self.clients.add(websocket)
        print(f"客户端已连接: {websocket.remote_address}")
        try:
            async for message in websocket:
                if self.message_handler:
                    self.message_handler(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"客户端已断开: {websocket.remote_address}")
            
    async def send_message(self, message: dict):
        """向所有连接的客户端发送消息"""
        if not self.clients:
            return
            
        json_message = json.dumps(message)
        # 创建副本避免在迭代时修改集合
        clients_copy = self.clients.copy()
        for client in clients_copy:
            try:
                await client.send(json_message)
            except websockets.exceptions.ConnectionClosed:
                self.clients.discard(client)
                
    def set_message_handler(self, handler: Callable):
        """设置消息处理器"""
        self.message_handler = handler


# 全局服务器实例
_ws_server: Optional[WebSocketServer] = None


def get_ws_server(host: str = "localhost", port: int = 8765) -> WebSocketServer:
    """获取WebSocket服务器实例（单例模式）"""
    global _ws_server
    if _ws_server is None:
        _ws_server = WebSocketServer(host, port)
    return _ws_server


async def start_ws_server(host: str = "localhost", port: int = 8765):
    """启动WebSocket服务器的便捷函数"""
    server = get_ws_server(host, port)
    await server.start()


async def stop_ws_server():
    """停止WebSocket服务器的便捷函数"""
    global _ws_server
    if _ws_server:
        await _ws_server.stop()
        _ws_server = None


async def send_ws_message(message: dict):
    """发送WebSocket消息的便捷函数"""
    global _ws_server
    if _ws_server:
        await _ws_server.send_message(message)
