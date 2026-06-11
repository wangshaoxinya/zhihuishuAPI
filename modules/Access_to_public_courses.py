import requests
from Crypto.Cipher import AES
import base64
import json

session = requests.session()
session.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
}

HOME_PAGE_AES_KEY = '7q9oko0vqb3la20r'
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


def Access_to_public_courses_cookie(cookie_str):
    """
    cookie入口函数
    :param cookie_str: 登录后的cookie字符串
    :return: 原始接口响应数据
    """
    session.cookies.set('acw_tc', cookie_str)
    url = 'https://onlineservice-api.zhihuishu.com/gateway/t/v1/student/course/share/queryShareCourseInfo'
    aes = AESEncrypt(key=HOME_PAGE_AES_KEY, iv=ZHS_AES_IV, mode=ZHS_AES_MODE)
    raw_data = '{"status":0,"pageNo":1,"pageSize":10}'
    secret_str = aes.aes_encrypt(raw_data)
    data = {"secretStr": secret_str}
    response = session.post(url, data=data)
    return response.json()


def Access_to_public_courses_date(cookie_str):
    """
    最终出口函数：返回格式化的共享学分课数据（兼容原有调用方式）
    :param cookie_str: 登录cookie
    :return: 课程列表 [{"Course Name": "", "secret": "", "Progress": ""}]
    """
    result = Access_to_public_courses_cookie(cookie_str)
    course_list = []
    
    if result.get('code') == 200:
        courses = result.get('result', {}).get('courseOpenDtos', [])
        for course in courses:
            item = {
                "Course Name": course.get('courseName', ''),
                "secret": course.get('secret', ''),
                "Progress": course.get('progress', '').replace('%', '')
            }
            course_list.append(item)
    
    return course_list


def Access_to_public_courses_full(cookie_str):
    """
    返回完整的课程信息（包含 recruitId 和 courseId）
    专供 examId_studentExamId.py 等需要真实 ID 的模块使用
    
    :param cookie_str: 登录cookie
    :return: 课程列表 [{
        "courseName": "",
        "secret": "",
        "progress": "",
        "recruitId": "",
        "courseId": ""
    }]
    """
    result = Access_to_public_courses_cookie(cookie_str)
    course_list = []
    
    if result.get('code') == 200:
        courses = result.get('result', {}).get('courseOpenDtos', [])
        for course in courses:
            item = {
                "courseName": course.get('courseName', ''),
                "secret": course.get('secret', ''),
                "progress": course.get('progress', '').replace('%', ''),
                "recruitId": course.get('recruitId', ''),
                "courseId": course.get('courseId', '')
            }
            course_list.append(item)
    
    return course_list


def get_course_by_secret(cookie_str, secret):
    """
    根据 secret 获取单个课程的完整信息（包含 recruitId 和 courseId）
    专供 examId_studentExamId.py 使用
    
    :param cookie_str: 登录cookie
    :param secret: 课程 secret 值
    :return: 课程信息字典 或 None
    """
    courses = Access_to_public_courses_full(cookie_str)
    for course in courses:
        if course.get('secret') == secret:
            return course
    return None


if __name__ == '__main__':
    # 使用示例
    cookie = input("请输入登录后的Cookie: ").strip()
    course_data = Access_to_public_courses_date(cookie)
    print(course_data)