import os
import re
import base64
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request, send_file
from openai import OpenAI

from services.retrieval_service import get_default_retrieval_service
from services.tts_service import (
    UnsupportedTTSLanguage,
    synthesize_speech,
)

load_dotenv()

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
POLICY_PATH = BASE_DIR / "policy.md"

BRAND_ASSETS = {
    "original": "images/huimango-original.png",
    "hero": "images/huimango-hero.png",
    "avatar": "images/huimango-avatar.png",
}

HOME_SERVICES = [
    {
        "topic_key": "admission",
        "emoji": "📚",
        "title": "入学准备",
        "summary": "入学前先了解资助支持",
    },
    {
        "topic_key": "loan",
        "emoji": "💰",
        "title": "助学贷款",
        "summary": "查看申请与还款提醒",
    },
    {
        "topic_key": "green",
        "emoji": "🏫",
        "title": "绿色通道",
        "summary": "暂时困难也能安心报到",
    },
    {
        "topic_key": "scholarship",
        "emoji": "🎓",
        "title": "国家助学金",
        "summary": "了解奖助项目与认定",
    },
    {
        "target": "questions",
        "emoji": "❓",
        "title": "常见问题",
        "summary": "学生家长关心的问题",
    },
]

TOPICS = {
    "admission": {
        "eyebrow": "新生入学支持",
        "title": "入学资助",
        "icon": "shield",
        "summary": "如果已经考上大学，但暂时交不起学费，不要轻易放弃入学机会。可以优先了解绿色通道、生源地信用助学贷款、国家助学金等政策。",
        "points": [
            "录取通知书里通常会附有资助政策材料，建议认真阅读。",
            "暂时缴费困难的新生，可关注高校绿色通道安排。",
            "家庭经济困难学生可了解生源地信用助学贷款和国家助学金。",
            "具体办理条件、材料和时间，以当地学生资助管理中心和学校最新通知为准。",
        ],
        "questions": [
            "考上大学但暂时交不起学费怎么办？",
            "什么是绿色通道？",
            "国家助学金怎么了解？",
            "申请资助一定会成功吗？",
        ],
    },
    "loan": {
        "eyebrow": "政策性贷款说明",
        "title": "助学贷款",
        "icon": "loan",
        "summary": "国家助学贷款是帮助家庭经济困难学生解决学费、住宿费等问题的重要政策性贷款，不是高利贷。办理时一定要走官方渠道。",
        "points": [
            "本专科生每人每年贷款额度最高不超过 20000 元，研究生最高不超过 25000 元。",
            "学生在校期间贷款利息由国家承担。",
            "贷款期限、利率、还款安排以官方政策和贷款合同为准。",
            "同一学年内，生源地信用助学贷款和校园地国家助学贷款不能同时申请。",
        ],
        "questions": [
            "助学贷款是不是高利贷？",
            "生源地信用助学贷款在哪里申请？",
            "首次申请助学贷款需要准备什么材料？",
            "共同借款人必须是父母吗？",
        ],
    },
    "green": {
        "eyebrow": "困难新生入学机制",
        "title": "绿色通道",
        "icon": "route",
        "summary": "绿色通道是高校帮助家庭经济困难新生先办理入学手续、再进行困难认定和后续资助的一种机制。",
        "points": [
            "绿色通道主要帮助暂时筹集不齐学费、住宿费的新生先入学。",
            "绿色通道不是自动免学费，也不等于一定获得所有资助。",
            "入学后通常还需要按学校要求完成困难认定和资助申请。",
            "具体办理方式以高校报到通知和学校资助部门要求为准。",
        ],
        "questions": [
            "什么是绿色通道？",
            "绿色通道是不是不用交学费？",
            "绿色通道需要准备什么？",
            "报到时交不起学费怎么办？",
        ],
    },
    "scholarship": {
        "eyebrow": "奖学金与助学金",
        "title": "奖助学金",
        "icon": "grant",
        "summary": "奖学金和助学金解决的问题不同。奖学金更强调奖励优秀，助学金更强调帮助家庭经济困难学生减轻生活压力。",
        "points": [
            "本专科国家奖学金奖励标准为每生每年 10000 元。",
            "本专科国家励志奖学金奖励标准为每生每年 6000 元。",
            "本专科国家助学金平均资助标准为每生每年 3700 元。",
            "具体评审条件、档次、名额和发放安排，以学校最新通知为准。",
        ],
        "questions": [
            "国家助学金和奖学金有什么区别？",
            "国家励志奖学金是什么？",
            "申请国家助学金需要什么条件？",
            "申请资助会不会丢人？",
        ],
    },
    "repay": {
        "eyebrow": "信用与还款提醒",
        "title": "诚信还款",
        "icon": "repay",
        "summary": "助学贷款是一份信用约定。毕业后应关注合同约定、还款日期和官方系统通知，按时还款，维护个人信用。",
        "points": [
            "正常申请资助或贷款本身不等于负面征信。",
            "如果办理助学贷款，应按合同和官方要求还款。",
            "逾期可能影响个人信用，具体影响以合同和官方政策为准。",
            "遇到升学、就业困难或家庭突发情况，应及时咨询官方渠道。",
        ],
        "questions": [
            "贷款什么时候开始还？",
            "毕业后忘记还款怎么办？",
            "提前还款应该注意什么？",
            "诚信还款为什么重要？",
        ],
    },
}

SYSTEM_PROMPT = """你是“惠心小助”，由惠州学院惠心筑梦实践队设计的 AI 资助政策问答助手。你的任务是面向学生、家长、社区群众和基层工作人员，用通俗、准确、温和、负责的语言解释国家资助政策、生源地信用助学贷款、绿色通道、国家助学金、勤工助学和诚信还款等内容。

回答要求：
1. 优先依据项目知识库回答；知识库没有明确依据时，不要编造。
2. 回答要比一句话更充实，适合政策宣传现场使用。一般按“直接结论 → 具体说明 → 可以怎么做 → 官方渠道提醒”的结构回答。
3. 对学生和家长要亲切、鼓励，不制造焦虑，不使用冷冰冰的公文腔。
4. 不代替官方部门进行资格认定，不承诺用户一定能申请成功。
5. 不收集、不要求用户提供身份证号、银行卡号、手机号、家庭详细住址、收入明细等敏感信息。
6. 涉及申请条件、办理地点、材料清单、贷款额度、还款规则、办理时间等内容时，必须提醒用户以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。
7. 遇到不确定问题，应建议用户咨询学校老师、县级学生资助管理中心或官方平台。
8. 如果用户询问与资助政策无关的问题，请礼貌提醒本助手主要用于资助政策咨询。
9. 不输出大段政策原文，不编造电话号码、网址、办理地点、工作人员姓名或内部渠道。
10. 可适当使用分点说明，但不要过长；普通问题建议 4-8 点以内。
"""

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
IMAGE_ERROR_MESSAGE = (
    "暂时无法完成图片解析。请确认图片清晰，或改用文字描述问题。"
    "如涉及具体办理事项，请咨询学校老师、县级学生资助管理中心或现场工作人员。"
)
VISION_NOT_CONFIGURED_MESSAGE = (
    "图片识别功能尚未配置，请先改用文字提问。管理员如需启用此功能，"
    "请配置支持图片输入的视觉模型；DeepSeek V4 文本模型不能直接识别图片。"
)
MAX_MESSAGE_LENGTH = 500
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TTS_TEXT_LENGTH = 3000
TTS_ERROR_MESSAGE = "云端朗读暂时不可用，网页将尝试使用设备自带语音。"


def request_timeout():
    try:
        return max(5.0, float(os.getenv("AI_TIMEOUT_SECONDS", "45")))
    except ValueError:
        return 45.0


def knowledge_retrieval_enabled():
    return os.getenv("USE_KNOWLEDGE_RETRIEVAL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def vision_config():
    api_key = os.getenv("VISION_API_KEY", "").strip()
    base_url = os.getenv("VISION_BASE_URL", "").strip()
    model = os.getenv("VISION_MODEL", "").strip()
    if not (api_key and base_url and model):
        return None
    return {"api_key": api_key, "base_url": base_url, "model": model}


def contains_sensitive_info(text):
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
    return f"""请根据以下政策知识库、安全规则和回答结构回答用户问题。

【政策知识库】
{policy_text}

【安全规则】
- 不要求用户提供身份证号、银行卡号、手机号、家庭详细住址、收入明细等敏感信息。
- 不承诺用户一定符合条件或一定能办理成功。
- 涉及具体条件、材料、流程、时间、额度、办理地点时，提醒用户以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。
- 如果知识库没有明确依据，请说明不确定，并建议咨询学校老师、县级学生资助管理中心或官方平台。
- 不编造电话号码、网址、内部渠道、工作人员姓名。

【回答结构建议】
1. 先用一句话直接回答。
2. 再用 3-6 点解释具体政策、办理思路或注意事项。
3. 最后加一句官方渠道提醒。
4. 对学生和家长保持鼓励、温和、易懂。

【用户问题】
{message}"""


def build_retrieval_user_prompt(message, retrieval_results):
    context_blocks = []
    for index, result in enumerate(retrieval_results, start=1):
        context_blocks.append(
            f"【相关知识片段 {index}】\n"
            f"文档：{result['title']}\n"
            f"章节：{result['section']}\n"
            f"内容：\n{result['content']}"
        )
    retrieval_context = "\n\n".join(context_blocks)

    return f"""请只根据以下检索到的相关知识片段、安全规则和回答结构回答用户问题。

【检索到的相关知识片段】
{retrieval_context}

【安全规则】
- 不要求用户提供身份证号、银行卡号、手机号、家庭详细住址、收入明细等敏感信息。
- 不承诺用户一定符合条件或一定能办理成功。
- 涉及具体条件、材料、流程、时间、额度、办理地点时，提醒用户以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。
- 如果相关知识片段没有明确依据，请说明不确定，并建议咨询学校老师、县级学生资助管理中心或官方平台。
- 不编造电话号码、网址、内部渠道、工作人员姓名或信息来源。

【回答结构建议】
1. 先用一句话直接回答。
2. 再用 3-6 点解释具体政策、办理思路或注意事项。
3. 最后加一句官方渠道提醒。
4. 对学生和家长保持鼓励、温和、易懂。

【用户问题】
{message}"""


def build_retrieval_metadata(retrieval_results):
    sources = []
    suggested_questions = []
    seen_sources = set()
    seen_questions = set()

    for result in retrieval_results:
        source = result.get("source") or {}
        source_item = {
            "title": source.get("title", ""),
            "organization": source.get("organization", ""),
            "url": result.get("url", ""),
            "updated_at": result.get("updated_at", ""),
        }
        source_key = tuple(source_item.values())
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append(source_item)

        for question in result.get("suggested_questions", []):
            if question and question not in seen_questions:
                seen_questions.add(question)
                suggested_questions.append(question)
            if len(suggested_questions) >= 3:
                break

    return sources, suggested_questions[:3]


def retrieve_knowledge_safely(message):
    if not knowledge_retrieval_enabled():
        return []
    try:
        return get_default_retrieval_service().retrieve(message)
    except Exception:
        app.logger.exception("Knowledge retrieval failed; falling back to policy.md")
        return []


def chat_payload(answer, *, sources=None, suggested_questions=None):
    return {
        "answer": answer,
        "sources": sources or [],
        "suggested_questions": suggested_questions or [],
    }


@app.get("/")
def index():
    return render_template(
        "index.html",
        topics=TOPICS,
        home_services=HOME_SERVICES,
        brand_assets=BRAND_ASSETS,
        vision_enabled=vision_config() is not None,
    )


@app.get("/topic/<topic_key>")
def topic(topic_key):
    topic_data = TOPICS.get(topic_key)
    if topic_data is None:
        abort(404)
    return render_template("topic.html", topic=topic_data)


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    # Reserved for backwards-compatible API evolution. Memory and audience
    # personalization are deliberately not implemented in this batch.
    _audience = data.get("audience", "")
    _history = data.get("history", [])

    if not message:
        return jsonify(chat_payload(EMPTY_MESSAGE))

    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify(chat_payload(TOO_LONG_MESSAGE))

    if contains_sensitive_info(message):
        return jsonify(chat_payload(PRIVACY_MESSAGE))

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return jsonify(chat_payload(NO_API_KEY_MESSAGE))

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=request_timeout(),
            max_retries=1,
        )
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        retrieval_results = retrieve_knowledge_safely(message)
        if retrieval_results:
            user_prompt = build_retrieval_user_prompt(message, retrieval_results)
            sources, suggested_questions = build_retrieval_metadata(retrieval_results)
        else:
            user_prompt = build_user_prompt(message, read_policy())
            sources, suggested_questions = [], []

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=1200,
            extra_body={"thinking": {"type": "disabled"}},
        )
        answer = (response.choices[0].message.content or "").strip()
        return jsonify(
            chat_payload(
                answer or API_ERROR_MESSAGE,
                sources=sources,
                suggested_questions=suggested_questions,
            )
        )
    except Exception:
        app.logger.exception("DeepSeek chat request failed")
        return jsonify(chat_payload(API_ERROR_MESSAGE)), 503


@app.post("/api/tts")
def text_to_speech():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    language = str(data.get("language", "zh-CN")).strip()

    if not text:
        return jsonify({"error": "请输入需要朗读的文字。", "fallback": True}), 400
    if len(text) > MAX_TTS_TEXT_LENGTH:
        return jsonify(
            {
                "error": f"朗读内容过长，请控制在 {MAX_TTS_TEXT_LENGTH} 字以内。",
                "fallback": True,
            }
        ), 400

    try:
        audio = synthesize_speech(text, language)
    except UnsupportedTTSLanguage:
        return jsonify({"error": "暂不支持该朗读语言。", "fallback": True}), 400
    except Exception:
        app.logger.exception("Cloud TTS request failed")
        return jsonify({"error": TTS_ERROR_MESSAGE, "fallback": True}), 503

    response = send_file(
        BytesIO(audio),
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="huimango-speech.mp3",
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-TTS-Provider"] = "edge-tts"
    return response


@app.post("/api/analyze-image")
def analyze_image():
    image = request.files.get("image")
    note = str(request.form.get("message", "")).strip()

    if image is None or not image.filename:
        return jsonify({"answer": "请先选择一张需要解析的图片。"}), 400

    content_type = image.content_type or ""
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        return jsonify({"answer": "目前仅支持 JPG、PNG、WebP 格式图片。"}), 400

    image_bytes = image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return jsonify({"answer": "图片过大，请上传 5MB 以内的清晰图片。"}), 400

    if len(note) > MAX_MESSAGE_LENGTH:
        return jsonify({"answer": TOO_LONG_MESSAGE}), 400

    if contains_sensitive_info(note):
        return jsonify({"answer": PRIVACY_MESSAGE}), 400

    config = vision_config()
    if config is None:
        return jsonify({"answer": VISION_NOT_CONFIGURED_MESSAGE}), 503

    prompt = (
        "请解析用户上传的图片内容。重点识别图片中与学生资助政策、助学贷款、绿色通道、"
        "奖助学金、还款、防诈骗或通知材料有关的信息。请先概括图片内容，再指出用户可能需要关注的事项。"
        "如果图片不清晰或无法判断，请说明原因。不要编造图片里没有出现的电话、地址、网址或办理结论。"
        "涉及具体办理条件、材料、流程、时间、额度时，提醒以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。"
    )
    if note:
        prompt += f"\n用户补充说明：{note}"

    try:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{content_type};base64,{encoded}"
        client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=request_timeout(),
            max_retries=1,
        )
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        answer = (response.choices[0].message.content or "").strip()
        return jsonify({"answer": answer or IMAGE_ERROR_MESSAGE})
    except Exception:
        app.logger.exception("Vision request failed")
        return jsonify({"answer": IMAGE_ERROR_MESSAGE}), 503


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
