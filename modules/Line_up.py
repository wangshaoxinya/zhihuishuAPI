"""
视频上报队列模块

接收批量视频数据，按队列顺序逐个传递给上报模块执行。
当出现安全验证时，清空队列中的剩余任务。
"""
import asyncio
import logging
from typing import Optional, Callable, List, Any

_logger = logging.getLogger("LineUp")

# 导入 Report_progress 模块设置队列状态
try:
    from modules.Report_progress import (
        Report_progress_set_queue_status,
        Report_progress_get_queue_status,
    )
except ImportError:
    # 如果导入失败，使用空函数
    def Report_progress_set_queue_status(running, total=0, current=0):
        pass
    def Report_progress_get_queue_status():
        return {"running": False, "total": 0, "current": 0}

# 队列状态
_queue: List[dict] = []
_is_running: bool = False
_current_index: int = 0
_on_next_callback: Optional[Callable] = None
_on_queue_empty_callback: Optional[Callable] = None
_on_clear_callback: Optional[Callable] = None


def set_on_next_handler(handler: Callable):
    """设置队列中下一个视频的处理回调（由 main_window 设置）"""
    global _on_next_callback
    _on_next_callback = handler


def set_on_queue_empty_handler(handler: Callable):
    """设置队列清空完成后的回调"""
    global _on_queue_empty_callback
    _on_queue_empty_callback = handler


def set_on_clear_handler(handler: Callable):
    """设置队列被安全验证清空时的回调"""
    global _on_clear_callback
    _on_clear_callback = handler


def enqueue(videos: List[dict]):
    """将视频列表加入队列

    Args:
        videos: 视频数据列表，每个元素包含视频的上报所需字段
    """
    global _queue
    _queue.extend(videos)
    _logger.info(f"已加入 {len(videos)} 个视频到队列，当前队列长度: {len(_queue)}")


def clear_queue():
    """清空队列（安全验证时调用）"""
    global _queue, _is_running, _current_index
    old_len = len(_queue)
    _queue.clear()
    _is_running = False
    _current_index = 0
    # 清除 Report_progress 队列运行状态
    Report_progress_set_queue_status(False, 0, 0)
    _logger.info(f"队列已清空，移除了 {old_len} 个待处理视频")

    if _on_clear_callback:
        try:
            if asyncio.iscoroutinefunction(_on_clear_callback):
                asyncio.create_task(_on_clear_callback(old_len))
            else:
                _on_clear_callback(old_len)
        except Exception as e:
            _logger.error(f"清空回调执行失败: {e}")


def get_queue_status() -> dict:
    """获取队列状态"""
    return {
        "total": len(_queue),
        "current_index": _current_index,
        "is_running": _is_running,
        "remaining": len(_queue) - _current_index if _is_running else len(_queue),
    }


async def start_queue():
    """启动队列处理"""
    global _is_running, _current_index

    if _is_running:
        _logger.warning("队列已在运行中")
        return

    if not _queue:
        _logger.info("队列为空，无需处理")
        return

    _is_running = True
    _current_index = 0
    # 设置 Report_progress 队列运行状态
    Report_progress_set_queue_status(True, len(_queue), 0)
    _logger.info(f"队列开始处理，共 {len(_queue)} 个视频")

    while _current_index < len(_queue):
        if not _is_running:
            # 队列被清空了（安全验证触发）
            _logger.info("队列处理已中断（被清空）")
            break

        video = _queue[_current_index]
        _logger.info(f"正在处理队列中的第 {_current_index + 1}/{len(_queue)} 个视频: {video.get('name', '未知')}")

        # 更新队列进度状态
        Report_progress_set_queue_status(True, len(_queue), _current_index + 1)

        if _on_next_callback:
            try:
                if asyncio.iscoroutinefunction(_on_next_callback):
                    result = await _on_next_callback(video, _current_index, len(_queue))
                else:
                    result = _on_next_callback(video, _current_index, len(_queue))
            except Exception as e:
                _logger.error(f"队列视频处理回调异常: {e}")
                result = {"code": -1, "message": f"处理异常: {e}"}

            # 检查结果：如果返回安全验证失败，清空队列
            if isinstance(result, dict):
                result_code = result.get("code", 0)
                result_message = result.get("message", "")

                # 安全验证触发：上报失败
                if result_code == -1:
                    _logger.warning(f"视频上报失败（可能触发安全验证），清空队列")
                    clear_queue()
                    break

        _current_index += 1

    _is_running = False
    # 清除 Report_progress 队列运行状态
    Report_progress_set_queue_status(False, 0, 0)

    # 队列处理完毕（正常完成或被清空），触发回调
    if _on_queue_empty_callback:
            try:
                if asyncio.iscoroutinefunction(_on_queue_empty_callback):
                    await _on_queue_empty_callback()
                else:
                    _on_queue_empty_callback()
            except Exception as e:
                _logger.error(f"队列清空回调执行失败: {e}")


def remove_completed_from_queue(video_id):
    """从队列中移除已完成的视频（单个视频完成时调用）"""
    global _current_index
    # 队列处理时，当前视频已完成，index 自然递增，无需额外操作
    pass


def is_queue_running() -> bool:
    """队列是否正在运行"""
    return _is_running


def get_queue_length() -> int:
    """获取队列剩余长度"""
    return len(_queue) - _current_index if _is_running else len(_queue)
