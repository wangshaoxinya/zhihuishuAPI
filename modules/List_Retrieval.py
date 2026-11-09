import requests
from Crypto.Cipher import AES
import base64
import time
import json

session = requests.session()
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
}

STUDY_VIDEO_AES_KEY = 'azp53h0kft7qi78q'
ZHS_AES_IV = '1g3qqdh4jvbskb9x'
ZHS_AES_MODE = AES.MODE_CBC


class AESEncrypt:
    def __init__(self, key, iv, mode):
        self.key = key.encode('utf-8')
        self.iv = iv.encode('utf-8')
        self.mode = mode

    def pkcs7padding(self, text):
        bs = 16
        length = len(text)
        bytes_length = len(text.encode('utf-8'))
        padding_size = length if (bytes_length == length) else bytes_length
        padding = bs - padding_size % bs
        padding_text = chr(padding) * padding
        self.coding = chr(padding)
        return text + padding_text

    def aes_encrypt(self, content):
        cipher = AES.new(self.key, self.mode, self.iv)
        content_padding = self.pkcs7padding(content)
        encrypt_bytes = cipher.encrypt(content_padding.encode('utf-8'))
        result = str(base64.b64encode(encrypt_bytes), encoding='utf-8')
        return result


def get_video_list(recruit_and_course_id, cookie_str=None):
    if cookie_str:
        session.cookies.set('acw_tc', cookie_str)
    
    url = 'https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/videolist'
    aes = AESEncrypt(key=STUDY_VIDEO_AES_KEY, iv=ZHS_AES_IV, mode=ZHS_AES_MODE)
    raw_data = f'{{"recruitAndCourseId":"{recruit_and_course_id}","dateFormate":{int(round(time.time()) * 1000)}}}'
    secret_str = aes.aes_encrypt(raw_data)
    data = {"secretStr": secret_str}
    response = session.post(url, data=data)
    return response.json()


def get_study_info(lesson_ids, lesson_video_ids, recruit_id, cookie_str=None):
    if cookie_str:
        session.cookies.set('acw_tc', cookie_str)
    
    url = 'https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/queryStuyInfo'
    aes = AESEncrypt(key=STUDY_VIDEO_AES_KEY, iv=ZHS_AES_IV, mode=ZHS_AES_MODE)
    lesson_ids_str = f'[{",".join([str(i) for i in lesson_ids])}]'
    lesson_video_ids_str = f'[{",".join([str(i) for i in lesson_video_ids])}]'
    raw_data = f'{{"lessonIds":{lesson_ids_str},"lessonVideoIds":{lesson_video_ids_str},"recruitId":{recruit_id},"dateFormate":{int(round(time.time()) * 1000)}}}'
    secret_str = aes.aes_encrypt(raw_data)
    data = {"secretStr": secret_str}
    response = session.post(url, data=data)
    return response.json()


def List_Retrieval_cookie(cookie_str=None):
    """
    弹出输入框让你输入 Cookie，并自动设置到请求里
    
    Args:
        cookie_str: 可选参数，如果提供则直接使用，否则弹出输入框
        
    Returns:
        你输入的 Cookie 字符串
        
    使用：
        cookie = List_Retrieval_cookie()
        # 或者
        cookie = List_Retrieval_cookie("your_cookie_here")
    """
    if cookie_str is None:
        cookie_str = input("请输入登录后的Cookie: ").strip()
    
    session.cookies.set('acw_tc', cookie_str)
    return cookie_str


def List_Retrieval_recruitAndCourseId(recruit_and_course_id=None):
    """
    弹出输入框输入课程 ID
    
    Args:
        recruit_and_course_id: 可选参数，如果提供则直接使用，否则弹出输入框
        
    Returns:
        你输入的 recruitAndCourseId
        
    使用：
        course_id = List_Retrieval_recruitAndCourseId()
        # 或者
        course_id = List_Retrieval_recruitAndCourseId("your_course_id")
    """
    if recruit_and_course_id is None:
        recruit_and_course_id = input("请输入课程ID(recruitAndCourseId): ").strip()
    
    return recruit_and_course_id


def List_Retrieval_date(cookie_str=None, recruit_and_course_id=None):
    """
    【最重要】自动执行整个流程（输入→获取视频→获取学习信息）
    
    Args:
        cookie_str: 可选参数，Cookie 字符串
        recruit_and_course_id: 可选参数，课程 ID
        
    Returns:
        结构化字典，包含学习数据：
        {
            "lesson": {},      # 章节信息
            "lv": {},          # 视频信息
            "all_data": {}     # 完整响应数据
        }
        
    使用：
        # 方式1：自动弹出输入框
        data = List_Retrieval_date()
        
        # 方式2：传入参数
        data = List_Retrieval_date(cookie="your_cookie", recruit_and_course_id="your_id")
        
        # 读取数据
        print(data["lesson"])
        print(data["lv"])
    """
    if cookie_str is None:
        cookie_str = List_Retrieval_cookie()
    else:
        session.cookies.set('acw_tc', cookie_str)
    
    if recruit_and_course_id is None:
        recruit_and_course_id = List_Retrieval_recruitAndCourseId()

    video_list_result = get_video_list(recruit_and_course_id)
    code = video_list_result.get('code')
    result_data = {"lesson": {}, "lv": {}, "all_data": {}}

    if code == 200 or code == 0:
        video_list_data = video_list_result.get('data', {})
        recruit_id = video_list_data.get('recruitId')
        video_chapters = video_list_data.get('videoChapterDtos', [])

        lesson_ids = []
        lesson_video_ids = []
        for chapter in video_chapters:
            for lesson in chapter.get('videoLessons', []):
                lesson_id = lesson.get('id')
                lesson_ids.append(lesson_id)
                for small_lesson in lesson.get('videoSmallLessons', []):
                    small_lesson_id = small_lesson.get('id')
                    lesson_video_ids.append(small_lesson_id)

        if lesson_ids:
            study_info_result = get_study_info(lesson_ids, lesson_video_ids, recruit_id)
            study_code = study_info_result.get('code')

            if study_code == 200 or study_code == 0:
                study_info = study_info_result.get('data', {})
                result_data["all_data"] = study_info_result
                if 'lesson' in study_info:
                    result_data["lesson"] = study_info['lesson']
                if 'lv' in study_info:
                    result_data["lv"] = study_info['lv']
    
    return result_data


if __name__ == '__main__':
    # 使用示例
    data = List_Retrieval_date()
    print(json.dumps(data, ensure_ascii=False, indent=2))