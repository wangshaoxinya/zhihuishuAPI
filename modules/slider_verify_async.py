"""
滑块验证码验证模块 - Qt WebEngine + qasync 版本

代码复用性高，可独立复制到其他项目使用。
"""
from types import ModuleType
import requests
import random
import logging
import asyncio
import json
from typing import Optional, Callable, Tuple, Any
from concurrent.futures import ThreadPoolExecutor

cv2: ModuleType = None
np: ModuleType = None
_logger = logging.getLogger("SliderVerify")
_executor = ThreadPoolExecutor(max_workers=2)


def set_logger(logger):
    """设置日志记录器"""
    global _logger
    _logger = logger


async def download_image_async(url):
    """异步下载图片并转换为 OpenCV 格式"""
    if not cv2 or not np:
        raise RuntimeError("OpenCV 或 NumPy 未初始化")

    def _download():
        response = requests.get(url, timeout=10)
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _download)


def process_background_image(image):
    """处理背景图片"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 100, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)
    return edges


def process_block_image(image):
    """处理滑块图片"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 100, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)
    return edges


def calculate_slider_position(bg_img, block_img) -> Tuple[int, int]:
    """计算滑块位置"""
    if not cv2 or not np:
        raise RuntimeError("OpenCV 或 NumPy 未初始化")

    bg_edges = process_background_image(bg_img)
    block_edges = process_block_image(block_img)

    result = cv2.matchTemplate(bg_edges, block_edges, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)

    return max_loc


def gen_movelist(sum_n, steps=30):
    """生成随机滑动鼠标位置列表"""
    move_list = []
    for x in range(steps - 1):
        if sum_n <= 1.5:
            break
        temp = random.uniform(1, sum_n / 2)
        move_list.append(round(temp, 3))
        sum_n -= temp
    move_list.append(round(sum_n, 3))
    return move_list


class CourseInfo:
    """课程信息数据类"""
    def __init__(self):
        self.course_name: str = ""
        self.secret: str = ""
        self.progress: float = 0.0
        self.course_id: str = ""
        self.other_info: dict = {}


class CourseListResult:
    """课程列表结果类"""
    def __init__(self):
        self.courses: list[CourseInfo] = []
        self.selected_course: CourseInfo = None
        self.all_completed: bool = False


class SliderVerifier:
    """滑块验证码验证器 - Qt WebEngine + qasync 版本"""

    def __init__(self, modules: list[ModuleType], log_callback: Optional[Callable] = None):
        """初始化验证器"""
        if len(modules) != 2:
            raise ValueError("modules 参数格式错误，应为 [numpy, cv2]")

        global cv2, np
        np, cv2 = modules
        self.log_callback = log_callback
        self.browser_engine = None

        if not cv2 or not np:
            self._log("OpenCV或Numpy导入失败,无法开启自动滑块验证.", "warn")

    async def Access_to_public_courses_cookie(self) -> str:
        """获取登录后的 Cookie 字符串"""
        if not self.browser_engine:
            self._log("浏览器引擎未设置", "error")
            return ""

        script = """
        (function() {
            return document.cookie;
        })();
        """

        result = await self._run_js_async(script)
        return result if result else ""

    async def Access_to_public_courses_date(self, cookie: str) -> CourseListResult:
        """调用接口获取课程信息列表（使用 AES 加密）
        
        Args:
            cookie: 登录后的 Cookie 字符串
            
        Returns:
            CourseListResult 对象，包含所有课程列表和第一个未完成的课程
        """
        result = CourseListResult()
        
        if not cookie:
            self._log("Cookie 为空，无法获取课程信息", "warn")
            return result

        try:
            def _fetch_courses():
                from .Access_to_public_courses import Access_to_public_courses_date
                return Access_to_public_courses_date(cookie)

            loop = asyncio.get_event_loop()
            course_list = await loop.run_in_executor(_executor, _fetch_courses)

            if course_list and isinstance(course_list, list) and len(course_list) > 0:
                for course_data in course_list:
                    course_info = CourseInfo()
                    course_info.course_name = course_data.get('Course Name', '')
                    course_info.secret = course_data.get('secret', '')
                    course_info.progress = float(course_data.get('Progress', 0))
                    course_info.course_id = ''
                    course_info.other_info = course_data
                    result.courses.append(course_info)
                    self._log(f"课程: {course_info.course_name}, 进度: {course_info.progress}%")

                result.selected_course = self._find_incomplete_course(result.courses)
                result.all_completed = result.selected_course is None

                if result.selected_course:
                    # self._log(f"选择未完成课程: {result.selected_course.course_name}")
                    pass
                else:
                    self._log("所有课程已完成")
            else:
                self._log("未获取到课程列表数据", "warn")

        except Exception as e:
            self._log(f"获取课程信息失败: {e}", "error")

        return result

    def _find_incomplete_course(self, courses: list[CourseInfo]) -> Optional[CourseInfo]:
        """查找第一个未完成的课程（进度 < 100%）"""
        for course in courses:
            if course.progress < 100.0:
                return course
        return None

    async def redirect_to_course(self, result: CourseListResult) -> bool:
        """根据课程进度判断并跳转到学习页面
        
        如果第一个课程进度为 100%，则选择下一个课程
        
        Args:
            result: CourseListResult 对象
            
        Returns:
            是否成功跳转
        """
        if not self.browser_engine:
            self._log("浏览器引擎未设置", "error")
            return False

        if result.all_completed:
            self._log("所有课程已完成，无需跳转")
            return False

        if result.selected_course:
            target_url = f"https://studyvideoh5.zhihuishu.com/stuStudy?recruitAndCourseId={result.selected_course.secret}"
            self._log(f"跳转至课程学习页面: {target_url}")
            self.browser_engine.load_url(target_url)
            return True

        return False

    def set_browser_engine(self, browser_engine):
        """设置浏览器引擎"""
        self.browser_engine = browser_engine

    def _log(self, msg: str, level: str = "info"):
        """记录日志"""
        if self.log_callback:
            self.log_callback(msg)
        if level == "warn":
            _logger.warning(msg)
        elif level == "error":
            _logger.error(msg)
        else:
            _logger.info(msg)

    async def _run_js_async(self, script: str, timeout: float = 5.0) -> Any:
        """异步执行 JavaScript"""
        if not self.browser_engine:
            raise RuntimeError("浏览器引擎未设置")

        future = asyncio.Future()

        def callback(result):
            if not future.done():
                future.set_result(result)

        self.browser_engine.run_javascript(script, callback)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._log("JavaScript 执行超时", "warn")
            return None

    async def verify(self, max_attempts: int = 3, offset: int = 0) -> bool:
        """执行滑块验证"""
        if not self.browser_engine:
            self._log("浏览器引擎未设置", "error")
            return False

        if not cv2 or not np:
            self._log("OpenCV或Numpy未初始化", "error")
            return False

        for attempt in range(max_attempts):
            try:
                await self._wait_for_captcha()
                max_loc = await self._get_slider_position()
                await self._move_slider(max_loc[0], offset)

                if await self._check_result():
                    self._log("滑块验证已成功通过!")
                    return True
                else:
                    self._log(f"第 {attempt + 1} 次验证未通过", "warn")

            except Exception as e:
                self._log(f"第{attempt+1}次验证失败: {e}", "warn")
                continue

        self._log("自动滑块验证失败,请手动验证!", "warn")
        return False

    async def _wait_for_captcha(self):
        """等待验证码加载"""
        for i in range(50):
            script = """
            (() => {
                const bg = document.querySelector('.yidun_bg-img');
                const block = document.querySelector('.yidun_jigsaw');
                const slider = document.querySelector('.yidun_slider');

                function isVisible(el) {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                }

                return JSON.stringify({
                    bgReady: !!bg && bg.complete && bg.naturalWidth > 0,
                    blockReady: !!block && block.complete && block.naturalWidth > 0,
                    sliderReady: !!slider && isVisible(slider)
                });
            })();
            """

            result_str = await self._run_js_async(script)
            result = json.loads(result_str) if result_str else {}

            if result.get("bgReady") and result.get("blockReady") and result.get("sliderReady"):
                await asyncio.sleep(0.5)
                return

            await asyncio.sleep(0.2)

        raise RuntimeError("等待验证码超时")

    async def _get_slider_position(self) -> Tuple[int, int]:
        """获取滑块位置"""
        script = """
        (function() {
            var bgImg = document.querySelector('.yidun_bg-img');
            var blockImg = document.querySelector('.yidun_jigsaw');
            var slider = document.querySelector('.yidun_slider');
            var track = document.querySelector('.yidun_bgimg') || 
                        (slider ? slider.parentElement : null);
            return JSON.stringify({
                bgUrl: bgImg ? bgImg.src : null,
                blockUrl: blockImg ? blockImg.src : null,
                bgNatWidth: bgImg ? bgImg.naturalWidth : 0,
                bgClientWidth: bgImg ? bgImg.clientWidth : 0,
                trackWidth: track ? track.clientWidth : 0
            });
        })();
        """

        result_str = await self._run_js_async(script)
        result = json.loads(result_str) if result_str else {}

        if not result.get('bgUrl') or not result.get('blockUrl'):
            raise RuntimeError("无法获取验证码图片")

        bg_img = await download_image_async(result['bgUrl'])
        block_img = await download_image_async(result['blockUrl'])

        if bg_img is None or block_img is None:
            raise RuntimeError("下载验证码图片失败")

        loop = asyncio.get_event_loop()
        pos = await loop.run_in_executor(
            _executor,
            calculate_slider_position,
            bg_img,
            block_img
        )

        bg_nat_w = result.get('bgNatWidth', bg_img.shape[1])
        bg_disp_w = result.get('bgClientWidth', result.get('trackWidth', bg_nat_w))
        if bg_disp_w == 0:
            bg_disp_w = bg_nat_w
        scale = bg_disp_w / bg_nat_w if bg_nat_w > 0 else 1.0
        display_x = pos[0] * scale + 10

        return (display_x, pos[1])

    async def _move_slider(self, distance: float, offset: int = 10):
        """移动滑块"""
        total_distance = distance + offset

        move_script = f"""
        (() => {{
            const slider = document.querySelector('.yidun_slider');
            const track = document.querySelector('.yidun_slider--normal') || 
                          document.querySelector('.yidun_bgimg') ||
                          slider.parentElement;
            if (!slider) return JSON.stringify({{success: false}});

            const sliderRect = slider.getBoundingClientRect();
            const trackRect = track ? track.getBoundingClientRect() : null;
            const startX = sliderRect.left + sliderRect.width / 2;
            const startY = sliderRect.top + sliderRect.height / 2;
            const trackWidth = trackRect ? trackRect.width : 280;
            const distance = {total_distance};

            function fire(type, x, y) {{
                slider.dispatchEvent(new MouseEvent(type, {{
                    bubbles: true,
                    cancelable: true,
                    clientX: x,
                    clientY: y
                }}));
            }}

            fire('mousedown', startX, startY);

            let current = 0;
            const steps = 30;

            function moveStep(i) {{
                if (i >= steps) {{
                    fire('mouseup', startX + distance, startY);
                    return;
                }}

                const progress = i / steps;
                const ease = 1 - Math.pow(1 - progress, 3);
                current = distance * ease;
                const jitter = Math.random() * 1.2;

                fire('mousemove', startX + current + jitter, startY + (Math.random() - 0.5));

                setTimeout(() => {{ moveStep(i + 1); }}, 8 + Math.random() * 18);
            }}

            moveStep(0);
            return JSON.stringify({{success: true, distance: distance, trackWidth: trackWidth}});
        }})();
        """

        await self._run_js_async(move_script)
        await asyncio.sleep(1.8)

    async def _check_result(self) -> bool:
        """检查验证结果"""
        await asyncio.sleep(1.5)

        script = """
        (function() {
            var modal = document.querySelector('.yidun_modal');
            var tipsText = document.querySelector('.yidun_tips__text');
            var tipsContent = tipsText ? tipsText.textContent : '';

            if (!modal || modal.style.display === 'none') {
                return JSON.stringify({passed: true});
            }

            var passWords = ['验证', '成功', '通过'];
            for (var i = 0; i < passWords.length; i++) {
                if (tipsContent.indexOf(passWords[i]) !== -1) {
                    return JSON.stringify({passed: true});
                }
            }

            return JSON.stringify({passed: false});
        })();
        """

        result_str = await self._run_js_async(script)
        result = json.loads(result_str) if result_str else {}
        return bool(result.get('passed'))


if __name__ == "__main__":
    print("滑块验证码验证模块")