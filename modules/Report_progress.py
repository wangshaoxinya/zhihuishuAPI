import base64
import json
import time
import random
import requests

from modules.encryption import encrypt_aes_cbc_pkcs7

_state = {
    "cookies": None,
    "recruitId": None,
    "courseId": None,
    "uuid": None,
    "bigLessionId": None,
    "smallLessionId": 0,
    "videoId": None,
    "chapterId": None,
    "videoSec": 0,
    "progress": 10,
    "record_id": None,
    "studyTotalTime": 0,
    "learnTime": "00:00:00",
    "pop_up_exam": [],
    "progress_callback": None,
    "is_processing": False,
    "processing_video_name": "",
    "processing_video_id": None,
    "queue_running": False,  # 队列运行状态
    "queue_total": 0,        # 队列总视频数
    "queue_current": 0,      # 队列当前处理索引
}

_key = "azp53h0kft7qi78q"
_iv = '31673371716468346a7662736b623978'
_headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "sec-ch-ua": "Not",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "Windows"
}


def _parse_cookie_string(cookie_str):
    cookies = {}
    if not cookie_str:
        return cookies
    items = cookie_str.split(';')
    for item in items:
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def _playing_encrypt(data_list):
    data_list = list(map(str, data_list))

    def Z(t):
        i = ";".join(t)
        return X(i)

    def X(t):
        _d = "zzpttjd"
        i = ""
        for h in range(len(t)):
            s = ord(t[h]) ^ ord(_d[h % 7])
            i += Y(s)
        return i

    def Y(t):
        t = hex(t)[2:]
        if len(t) < 2:
            t = "0" + t
        return t[-4:]

    return Z(data_list)


def Report_progress_cookie_one(cookie_str):
    _state["cookies"] = _parse_cookie_string(cookie_str)


def Report_progress_recruitId(recruitId):
    _state["recruitId"] = recruitId


def Report_progress_courseId(courseId):
    _state["courseId"] = courseId


def Report_progress_uuid(uuid):
    _state["uuid"] = uuid


def Report_progress_bigLessionId(bigLessionId):
    _state["bigLessionId"] = bigLessionId


def Report_progress_smallLessionId(smallLessionId):
    _state["smallLessionId"] = smallLessionId


def Report_progress_videoId(videoId):
    _state["videoId"] = videoId


def Report_progress_chapterId(chapterId):
    _state["chapterId"] = chapterId


def Report_progress_videoSec(videoSec):
    _state["videoSec"] = videoSec


def Report_progress_Progress(seconds):
    _state["progress"] = seconds


def Report_progress_set_callback(callback):
    """设置进度回调函数，每次上报后调用 callback(current_time, total_time)"""
    _state["progress_callback"] = callback


def Report_progress_video_name(video_name: str):
    """设置当前处理的视频名称（用于提示信息）"""
    _state["processing_video_name"] = video_name


def Report_progress_set_queue_status(running: bool, total: int = 0, current: int = 0):
    """设置队列运行状态（供 Line_up 模块调用）"""
    _state["queue_running"] = running
    _state["queue_total"] = total
    _state["queue_current"] = current


def Report_progress_get_queue_status() -> dict:
    """获取队列运行状态"""
    return {
        "running": _state["queue_running"],
        "total": _state["queue_total"],
        "current": _state["queue_current"],
    }


def Report_progress_is_busy() -> bool:
    """检查是否正在处理（单任务或队列）"""
    return _state["is_processing"] or _state["queue_running"]


def _get_pre_learning_note(cookies, courseId, chapterId, bigLessionId, smallLessionId, recruitId, videoId):
    headers = {
        "Origin": "https://studyvideoh5.zhihuishu.com",
        "Referer": "https://studyvideoh5.zhihuishu.com/",
    }
    headers.update(_headers)
    url = "https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/prelearningNote"
    data_to_encrypt = {
        "ccCourseId": courseId,
        "chapterId": chapterId,
        "isApply": 1,
        "lessonId": bigLessionId,
        "lessonVideoId": smallLessionId,
        "recruitId": recruitId,
        "videoId": videoId,
    }
    data = {
        "secretStr": encrypt_aes_cbc_pkcs7(str(data_to_encrypt).replace("'", '"'), _key, _iv),
        "dateFormate": str(int(time.time() * 1000))
    }
    try:
        response = requests.post(url, cookies=cookies, data=data, headers=headers)
        response.raise_for_status()
    except Exception as e:
        return -1
    try:
        result = response.json()
        studied_lesson = result["data"]["studiedLessonDto"]
        return {
            "record_id": studied_lesson.get("id"),
            "studyTotalTime": studied_lesson.get("studyTotalTime", 0),
            "learnTime": studied_lesson.get("learnTime", "00:00:00")
        }
    except Exception as e:
        return -1


def _report_once(cookies, recruitId, courseId, uuid, bigLessionId, smallLessionId, videoId, chapterId, record_id, playtime, studyTotalTime, learnTime):
    total = studyTotalTime
    hours = total // 3600
    minutes = (total - hours * 3600) // 60
    seconds_val = total - hours * 3600 - minutes * 60
    learnTime = "%02d:%02d:%02d" % (hours, minutes, seconds_val)
    watch_point = "0,1," + str(round(studyTotalTime / 5) + 2)

    this_video_data = [
        recruitId,
        bigLessionId,
        smallLessionId,
        videoId,
        chapterId,
        "0",
        playtime,
        studyTotalTime,
        learnTime,
        uuid + "zhs"
    ]
    post_data = {
        'ewssw': watch_point,
        'sdsew': _playing_encrypt(this_video_data),
        'zwsds': str(base64.b64encode(str(record_id).encode("utf-8"))).replace("b'", "").replace("'", ""),
        'courseId': courseId,
    }
    data = "secretStr=" + encrypt_aes_cbc_pkcs7(str(post_data).replace("'", '"'), _key, _iv)

    headers = {
        "Accept": "*/*",
        "Origin": "https://studyvideoh5.zhihuishu.com",
        "Referer": "https://studyvideoh5.zhihuishu.com/",
    }
    headers.update(_headers)
    url = "https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/saveDatabaseIntervalTimeV2"
    try:
        response = requests.post(url, cookies=cookies, data=data, headers=headers)
        response.raise_for_status()
    except Exception as e:
        return -1
    try:
        result = response.json()
        if result.get("code") == 0:
            return result
        else:
            return -1
    except Exception as e:
        return -1


def Report_progress_Output():
    # 检查是否有其他视频正在上报（包括单任务和队列）
    if _state["is_processing"]:
        current_video_id = _state["videoId"]
        processing_video_name = _state["processing_video_name"]
        processing_video_id = _state["processing_video_id"]
        
        # 打印提示信息
        print(f"⚠️ 检测到重复上报请求！")
        print(f"   当前正在处理: {processing_video_name or '未知视频'} (ID: {processing_video_id})")
        print(f"   尝试请求的视频: ID {current_video_id}")
        print(f"   请等待当前视频处理完成后再操作")
        print(f"   如需取消当前任务，请刷新页面或重启应用")
        
        # 不调用进度回调，避免显示 -1/-1 的进度
        return {"code": -2, "message": "检测到重复上报，当前有视频正在处理"}
    
    # 设置处理状态
    _state["is_processing"] = True
    _state["processing_video_id"] = _state["videoId"]
    
    try:
        cookies = _state["cookies"]
        recruitId = _state["recruitId"]
        courseId = _state["courseId"]
        uuid = _state["uuid"]
        bigLessionId = _state["bigLessionId"]
        smallLessionId = _state["smallLessionId"]
        videoId = _state["videoId"]
        chapterId = _state["chapterId"]
        videoSec = _state["videoSec"]
        progress = _state["progress"]

        pre = _get_pre_learning_note(cookies, courseId, chapterId, bigLessionId, smallLessionId, recruitId, videoId)
        if pre == -1:
            return {"code": -1, "message": "获取学习记录失败"}

        record_id = pre["record_id"]
        studyTotalTime = pre["studyTotalTime"]

        if studyTotalTime >= videoSec:
            return {"code": 0, "message": "already completed"}

        start_block = studyTotalTime // progress
        total_blocks = videoSec // progress
        if videoSec % progress != 0:
            total_blocks += 1

        callback = _state.get("progress_callback")

        for i in range(start_block, total_blocks):
            # 每次上报随机 5~20 秒
            playtime = random.randint(5, 20)
            studyTotalTime += playtime

            if studyTotalTime > videoSec:
                playtime = studyTotalTime - videoSec
                studyTotalTime = videoSec

            learnTime = ""
            result = _report_once(cookies, recruitId, courseId, uuid, bigLessionId, smallLessionId, videoId, chapterId, record_id, playtime, studyTotalTime, learnTime)

            # 回调打印进度（包含接口返回信息）
            if callback:
                try:
                    callback(studyTotalTime, videoSec, result)
                except Exception:
                    pass

            # 如果上报失败，立即停止（不重试）
            if result == -1:
                return {"code": -1, "message": "上报失败，已停止", "studyTotalTime": studyTotalTime, "videoSec": videoSec}

            if studyTotalTime >= videoSec:
                break

            # 每次上报之间间隔1秒
            time.sleep(1)

        return {"code": 0, "message": "completed", "studyTotalTime": studyTotalTime, "videoSec": videoSec}
    
    finally:
        # 无论成功还是失败，都要重置处理状态
        _state["is_processing"] = False
        _state["processing_video_name"] = ""
        _state["processing_video_id"] = None
