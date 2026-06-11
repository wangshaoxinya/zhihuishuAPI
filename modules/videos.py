import json
import time
import requests
from modules.encryption import encrypt_aes_cbc_pkcs7

class VideoFetcher:
    def __init__(self, cookie_str: str):
        self.cookies = self._parse_cookie_string(cookie_str)
        self.class_list = None
        self.video_data = None
        self.videoChapterDtos = None
        self.courseId = None
        self.recruitId = None
        self.study_info = None
        self.class_data = {
            "recruitAndCourseId": "",
            "dateFormate": 1703671623000
        }
        self.key = "azp53h0kft7qi78q"
        self.iv = '31673371716468346a7662736b623978'
        self.headers = {
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

    def _parse_cookie_string(self, cookie_str: str) -> dict:
        cookies = {}
        if not cookie_str:
            return cookies
        items = cookie_str.split(';')
        for item in items:
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                key = key.strip()
                value = value.strip()
                cookies[key] = value
        return cookies

    def set_course(self, recruit_and_course_id: str):
        self.class_data["recruitAndCourseId"] = recruit_and_course_id

    def get_videolist(self):
        headers = {
            "Origin": "https://studyvideoh5.zhihuishu.com",
            "Referer": "https://studyvideoh5.zhihuishu.com/",
        }
        headers.update(self.headers)
        url = "https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/videolist"
        data = "secretStr=" + encrypt_aes_cbc_pkcs7(str(self.class_data).replace("'", '"'), self.key, self.iv)
        try:
            response = requests.post(url, headers=headers, cookies=self.cookies, data=data)
            response.raise_for_status()
        except Exception:
            return -1
        try:
            response_json = response.json()
            self.recruitId = response_json["data"]["recruitId"]
            self.courseId = response_json["data"]["courseId"]
            self.videoChapterDtos = response_json["data"]["videoChapterDtos"]
            return response_json
        except Exception:
            return -1

    def get_study_info(self):
        if not self.videoChapterDtos:
            return -1
        headers = {
            "Accept": "*/*",
            "Origin": "https://studyvideoh5.zhihuishu.com",
            "Referer": "https://studyvideoh5.zhihuishu.com/",
        }
        headers.update(self.headers)
        url = "https://studyservice-api.zhihuishu.com/gateway/t/v1/learning/queryStuyInfo"
        all_class = {}
        lessonIds = []
        lessonVideoIds = []
        video_data = {}
        for chapter in self.videoChapterDtos:
            for lesson in chapter.get("videoLessons", []):
                lesson_id = lesson.get("id")
                lessonIds.append(lesson_id)
                if lesson.get("ishaveChildrenLesson", False):
                    for small_lesson in lesson.get("videoSmallLessons", []):
                        small_id = small_lesson.get("id")
                        lessonVideoIds.append(small_id)
                        video_data[str(small_id)] = {
                            "name": small_lesson.get("name", ""),
                            "videoId": small_lesson.get("videoId", ""),
                            "chapterId": lesson.get("chapterId", ""),
                            "videoSec": small_lesson.get("videoSec", 0),
                            "bigLessionId": lesson_id,
                            "smallLessionId": small_id
                        }
                else:
                    video_data[str(lesson_id)] = {
                        "name": lesson.get("name", ""),
                        "videoId": lesson.get("videoId", ""),
                        "chapterId": lesson.get("chapterId", ""),
                        "videoSec": lesson.get("videoSec", 0),
                        "bigLessionId": lesson_id,
                        "smallLessionId": 0
                    }
        all_class["recruitId"] = self.recruitId
        all_class["lessonVideoIds"] = lessonVideoIds
        all_class["lessonIds"] = lessonIds
        data = "secretStr=" + encrypt_aes_cbc_pkcs7(str(all_class).replace("'", '"'), self.key, self.iv)
        try:
            response = requests.post(url, headers=headers, cookies=self.cookies, data=data)
            response.raise_for_status()
        except Exception:
            return -1
        try:
            self.study_info = response.json()["data"]
            if "lv" in self.study_info:
                for video_id, video_info in self.study_info["lv"].items():
                    try:
                        video_data[str(video_id)].update(video_info)
                    except KeyError:
                        pass
            for video_id, video_info in self.study_info["lesson"].items():
                try:
                    video_data[str(video_id)].update(video_info)
                except KeyError:
                    pass
            self.video_data = video_data
            return video_data
        except Exception:
            return -1

    def get_real_name(self):
        headers = {
            "Origin": "https://studyvideoh5.zhihuishu.com",
            "Referer": "https://studyvideoh5.zhihuishu.com/",
        }
        headers.update(self.headers)
        url = "https://studyservice-api.zhihuishu.com/gateway/f/v1/login/getLoginUserInfo"
        params = {
            "dateFormate": str(int(time.time() * 1000))
        }
        try:
            response = requests.get(url, cookies=self.cookies, params=params, headers=headers)
            response.raise_for_status()
            json_data = response.json()
            real_name = json_data.get("data", {}).get("realName")
            if real_name:
                return real_name
        except Exception:
            pass
        try:
            import urllib.parse
            caslogc = self.cookies.get("CASLOGC", "")
            if caslogc:
                decoded = urllib.parse.unquote(caslogc)
                cas_data = json.loads(decoded)
                real_name = cas_data.get("realName", "")
                if real_name:
                    return real_name
        except Exception:
            pass
        return -1

# ===================== 【保留】获取 recruitAndCourseId 函数 =====================
def recruitAndCourse_id(cookie_str: str):
    fetcher = VideoFetcher(cookie_str)
    class_list = fetcher.get_all_class()
    if class_list == -1:
        return []
    result = []
    for course in class_list:
        result.append({
            "course_name": course["name"],
            "recruitAndCourseId": course["recruitAndCourseId"]
        })
    return result

# ===================== 【保留】Cookie + ID 获取视频信息 =====================
def video_cookie_one(cookie_str: str, recruit_and_course_id: str):
    fetcher = VideoFetcher(cookie_str)
    result = {
        "videos": None,
        "study_info": None,
        "real_name": None
    }
    result["real_name"] = fetcher.get_real_name()
    fetcher.set_course(recruit_and_course_id)
    videos = fetcher.get_videolist()
    if videos != -1:
        result["videos"] = videos
        study = fetcher.get_study_info()
        if study != -1:
            result["study_info"] = study
    return result

# ===================== 【保留】格式化输出函数 =====================
def video_output(result):
    return json.dumps(result, ensure_ascii=False, indent=2)

# ===================== 精简后主程序：只输入Cookie和ID =====================
if __name__ == "__main__":
    cookie_str = input("请粘贴你的Cookie：").strip()
    course_id = input("请输入课程 recruitAndCourseId：").strip()
    
    result = video_cookie_one(cookie_str, course_id)
    output = video_output(result)
    # print(output)