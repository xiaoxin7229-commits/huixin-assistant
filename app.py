import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
POLICY_PATH = BASE_DIR / "policy.md"

SYSTEM_PROMPT = """你是“惠心小助”，由惠州学院惠心筑梦实践队设计的 AI 资助政策问答助手。你的任务是面向学生、家长和社区群众，用通俗、准确、温和的语言解释国家资助政策、生源地信用助学贷款、绿色通道、国家助学金、勤工助学和诚信还款等内容。

回答要求：
1. 优先依据项目知识库与官方政策资料回答。
2. 回答要简洁、亲切、通俗，适合学生和家长理解。
3. 不代替官方部门进行资格认定。
4. 不承诺用户一定能申请成功。
5. 不收集、不要求用户提供身份证号、银行卡号、手机号、家庭详细住址、收入明细等敏感信息。
6. 涉及申请条件、办理地点、材料清单、贷款额度、还款规则等内容时，必须提醒用户以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。
7. 遇到不确定问题，不要编造，应该建议用户咨询学校老师、县级学生资助管理中心或官方平台。
8. 如果用户询问与资助政策无关的问题，请礼貌提醒本助手主要用于资助政策咨询。
9. 回答结构建议为：先直接回答，再解释原因或流程，最后给出官方渠道提醒。
10. 不输出长篇政策原文，不编造电话号码、网址、办理地点或工作人员姓名。"""

EMPTY_MESSAGE = "请输入你的问题。"
TOO_LONG_MESSAGE = "问题过长，请简要描述，建议控制在500字以内。"
PRIVACY_MESSAGE = (
    "为了保护个人隐私，请不要在本助手中输入身份证号、银行卡号、手机号、家庭详细住址、"
    "收入明细等敏感信息。如需办理具体业务，请通过官方平台、学校老师或现场工作人员咨询。"
)
NO_API_KEY_MESSAGE = "当前问答服务还没有配置 DeepSeek API Key，请管理员在 .env 文件中填写密钥后重启服务。"
API_ERROR_MESSAGE = (
    "暂时无法连接问答服务，请稍后再试。如现场急需咨询，请联系学校老师、"
    "县级学生资助管理中心或现场工作人员。"
)


def contains_sensitive_info(text):
    """Detect obvious personal sensitive information before calling the API."""
    patterns = [
        r"\b[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",
        r"(?<!\d)1[3-9]\d{9}(?!\d)",
        r"(?<!\d)\d{13,19}(?!\d)",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def read_policy():
    if not POLICY_PATH.exists():
        return "政策知识库暂未配置。回答时请提醒用户以官方渠道为准。"
    return POLICY_PATH.read_text(encoding="utf-8")


def build_user_prompt(message, policy_text):
    return f"""请根据以下政策知识库和安全规则回答用户问题。

【政策知识库】
{policy_text}

【安全规则】
- 不要求用户提供身份证号、银行卡号、手机号、家庭详细住址、收入明细等敏感信息。
- 不承诺用户一定符合条件或一定能办理成功。
- 涉及具体条件、材料、流程、时间、额度、办理地点时，提醒用户以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。
- 如果知识库没有明确依据，请说明不确定，并建议咨询学校老师、县级学生资助管理中心或官方平台。

【用户问题】
{message}"""


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"answer": EMPTY_MESSAGE})

    if len(message) > 500:
        return jsonify({"answer": TOO_LONG_MESSAGE})

    if contains_sensitive_info(message):
        return jsonify({"answer": PRIVACY_MESSAGE})

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return jsonify({"answer": NO_API_KEY_MESSAGE})

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        policy_text = read_policy()

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(message, policy_text)},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        answer = response.choices[0].message.content.strip()
        return jsonify({"answer": answer or API_ERROR_MESSAGE})
    except Exception:
        return jsonify({"answer": API_ERROR_MESSAGE})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
