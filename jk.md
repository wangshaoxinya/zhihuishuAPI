# 智慧树刷题接口文档

> 所以接口均需要使用cookie和o_session_id

## 1. 获取答案接口

**接口地址**: `POST https://zhs.shaoxin.top/ebpage/app/answer`

**请求参数**:

- `questions`: 题目列表（JSON 数组）
  - 每个题目包含:
    - `eid`: 题目 ID
    - `name`: 题目名称
    - `questionType`: 题目类型（1-单选, 2-多选, 14-判断）
    - `options`: 选项列表（每个选项包含 `id`, `content`）

---

## 2. 获取作业列表接口

**接口地址**: `POST https://studentexam-api.zhihuishu.com/studentExam/gateway/t/v1/student/getStudentHomework`

**请求参数**:

- `recruitId`: 招生 ID（字符串）
- `courseId`: 课程 ID（字符串）
- `cookie`: 用户 Cookie（必须包含 o_session_id）
- `flag`: 1（单元测试）

---

## 3. 获取学生考试ID接口

**接口地址**: `POST https://studentexam-api.zhihuishu.com/studentExam/gateway/t/v1/student/getStudentHomework`

**请求参数**:

- `courseId`: 课程 ID（字符串）
- `recruitId`: 招生 ID（字符串）

---

## 4. 获取题目接口

**接口地址**: `POST https://studentexam-api.zhihuishu.com/studentExam/gateway/t/v1/student/doHomework`

**请求参数**:

- `recruitId`: 招生 ID（字符串）
- `examId`: 考试 ID（字符串）
- `studentExamId`: 学生考试 ID（字符串）
- `schoolId`: 学校 ID（字符串）
- `courseId`: 课程 ID（字符串）
- `cookie`: 用户 Cookie（必须包含 o_session_id）


---

## 5. 保存答案接口

**接口地址**: `POST https://studentexam-api.zhihuishu.com/studentExam/gateway/t/v1/answer/saveStudentAnswer`

**请求参数**:

- `examId`: 考试 ID（字符串）
- `recruitId`: 招生 ID（字符串）
- `stuExamId`: 学生考试 ID（字符串）
- `schoolId`: 学校 ID（字符串）
- `answers`: 答案列表（JSON 数组）
  - 每个答案包含:
    - `eid`: 题目 ID
    - `answer`: 答案（单选/判断为整数，多选为逗号分隔字符串）
    - `questionType`: 题目类型（1-单选, 2-多选, 14-判断）

---

## 题目类型说明

| questionType | 说明   |
| ------------ | ------ |
| 1            | 单选题 |
| 2            | 多选题 |
| 14           | 判断题 |

---

## 6. 提交作业接口

**接口地址**: `POST https://studentexam-api.zhihuishu.com/studentExam/gateway/t/v1/answer/submit`

**请求参数**:

- `recruitId`: 招生 ID（字符串）
- `examId`: 考试 ID（字符串）
- `stuExamId`: 学生考试 ID（字符串）
- `achieveCount`: 作业题目数量（整数，如 10）

---

## 免责声明

本文档仅供学习交流使用，作者不对因使用本文档内容所导致的任何损失或损害承担责任。使用本文档中的接口和方法所产生的任何后果由使用者自行承担。请遵守相关法律法规和平台规定，合理使用。
