"""Keyword and synonym rules for the lightweight knowledge retriever."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


NON_TEXT = re.compile(r"[^0-9a-z\u4e00-\u9fff]+", re.IGNORECASE)

# Canonical terms are added when any listed oral expression is found. The
# Vocabulary covers the published MVP domains while keeping deterministic,
# standard-library-only matching.
SYNONYM_GROUPS: dict[str, tuple[str, ...]] = {
    "学生资助": (
        "学生资助",
        "资助政策",
        "家庭经济困难",
        "困难学生",
        "没钱上学",
        "上不起学",
        "读不起书",
    ),
    "国家助学金": ("国家助学金", "助学金", "生活补助"),
    "助学贷款": (
        "助学贷款",
        "国家贷款",
        "大学贷款",
        "借钱读书",
        "读书贷款",
        "上学贷款",
        "贷款",
    ),
    "学费": ("交不起学费", "没钱交学费", "学费困难", "缴费困难", "学费"),
    "绿色通道": ("绿色通道", "先入学", "先报到"),
    "家庭经济困难认定": ("家庭经济困难认定", "困难认定", "贫困认定"),
    "国家奖学金": ("国家奖学金", "奖学金"),
    "国家励志奖学金": ("励志奖学金", "国家励志奖学金"),
    "还款": ("提前还款", "什么时候还款", "还款", "还贷", "逾期", "征信"),
    "生源地信用助学贷款": ("生源地信用助学贷款", "生源地贷款", "生源地"),
    "共同借款人": ("共同借款人", "共同贷款人"),
    "续贷": ("续贷", "继续贷款"),
    "官方渠道": ("官方渠道", "官方网站", "官网", "学生在线系统"),
    "资助申请流程": (
        "怎么申请",
        "怎么办理",
        "申请流程",
        "需要什么材料",
        "什么时候申请",
        "去哪里申请",
        "去哪申请",
        "材料不齐",
        "错过申请",
    ),
    "官方咨询": (
        "咨询电话",
        "联系电话",
        "官方电话",
        "服务热线",
        "95593",
        "系统网址",
        "官方系统",
    ),
    "广东学生资助": (
        "广东学生资助",
        "广东资助政策",
        "广东助学政策",
        "广东省教育厅",
    ),
    "惠州本地": ("惠州", "惠东", "惠州本地", "本地政策"),
    "农产品服务": (
        "助农",
        "农产品",
        "农户",
        "种植户",
        "直播带货",
        "农业营销",
        "12221",
    ),
    "农产品物流": ("冷链", "农产品物流", "包装运输", "生鲜配送"),
    "社区服务": ("社区服务", "社区办事", "社区窗口", "线下办事"),
    "志愿服务": ("志愿服务", "志愿者", "志愿活动"),
    "社区照护": ("社区托育", "婴幼儿照护", "老年人办事", "人工帮办"),
    "智慧社区": ("智慧社区", "人脸识别", "社区门禁", "社区监控"),
    "青年就业": ("青年就业", "高校毕业生", "离校未就业", "找工作"),
    "青年创业": ("青年创业", "创业补贴", "创业贷款", "返乡创业"),
    "毕业档案": ("档案转递", "毕业去向", "学生档案"),
    "求职安全": ("求职防骗", "黑中介", "培训贷", "招聘押金"),
    "基层就业": ("基层就业", "乡村就业", "学费补偿", "贷款代偿"),
}

DOMAIN_TERMS: dict[str, tuple[str, ...]] = {
    "student-aid": (
        "学生资助",
        "国家助学金",
        "助学贷款",
        "学费",
        "绿色通道",
        "家庭经济困难认定",
        "国家奖学金",
        "国家励志奖学金",
        "还款",
        "生源地信用助学贷款",
        "共同借款人",
        "续贷",
        "资助申请流程",
        "官方咨询",
        "广东学生资助",
    ),
    "shared": ("官方渠道",),
    "local": ("惠州本地",),
    "agriculture": ("农产品服务", "农产品物流"),
    "community": ("社区服务", "志愿服务", "社区照护", "智慧社区"),
    "youth": ("青年就业", "青年创业", "毕业档案", "求职安全", "基层就业"),
}


@dataclass(frozen=True)
class KeywordAnalysis:
    normalized_question: str
    terms: tuple[str, ...]
    domains: tuple[str, ...]


def normalize_text(value: str) -> str:
    """Normalize Chinese and Latin text for deterministic substring matching."""

    return NON_TEXT.sub("", str(value).lower())


def analyze_question(
    question: str,
    *,
    metadata_keywords: Iterable[str] = (),
) -> KeywordAnalysis:
    """Extract canonical terms, oral aliases and likely knowledge domains."""

    normalized_question = normalize_text(question)
    if not normalized_question:
        return KeywordAnalysis("", (), ())

    matched_terms: set[str] = set()
    canonical_matches: set[str] = set()

    for canonical, aliases in SYNONYM_GROUPS.items():
        for alias in aliases:
            if normalize_text(alias) in normalized_question:
                canonical_matches.add(canonical)
                matched_terms.add(canonical)
                matched_terms.add(alias)

    for keyword in metadata_keywords:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword and normalized_keyword in normalized_question:
            matched_terms.add(keyword)

    domains = {
        domain
        for domain, domain_terms in DOMAIN_TERMS.items()
        if any(term in canonical_matches for term in domain_terms)
    }

    return KeywordAnalysis(
        normalized_question=normalized_question,
        terms=tuple(sorted(matched_terms, key=lambda item: (-len(normalize_text(item)), item))),
        domains=tuple(sorted(domains)),
    )
