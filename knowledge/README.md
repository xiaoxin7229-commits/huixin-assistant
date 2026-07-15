# 惠芒go 知识库维护说明

## 国家资助政策知识库V1.0

第五批次在现有 `student-aid/` 体系中新增生源地贷款、广东学生资助、办理流程、术语、官方渠道和100条FAQ。文件继续使用小写英文与连字符命名，正式元数据以 `catalog.json` 为准。

统一回答规范位于 `prompts/student-aid-answer-guidelines.md`，由轻量检索服务在国家资助问题的首个知识片段中安全注入；读取失败时自动忽略，不影响网站启动。

维护记录见 `knowledge-update-notes.md` 和 `test-report.md`。

`knowledge/` 是惠芒go 2.0 的结构化知识库。第三批次按现场展示 MVP 原则，将五份用户提供的 PDF 拆分为面向问题场景的 Markdown 文档；现有灰度开关启用时，只有 `published` 文档会进入 RAG 检索。

## 目录与命名

- `shared/`：跨领域服务边界、隐私安全和官方渠道。
- `student-aid/`：国家学生资助知识及本批次 PDF 迁移草稿。
- `local/`：惠州、惠东本地办事与核验知识。
- `agriculture/`：助农营销、产销和物流知识。
- `community/`：社区办事、志愿服务、托育与隐私知识。
- `youth/`：青年就业、创业、档案和求职安全知识。
- `education-growth/`、`employment/`：后续领域预留目录。
- 所有知识文件使用小写英文和连字符命名。

## catalog.json 字段

每条文档记录必须包含：`id`、`title`、`file`、`domain`、`audiences`、`region`、`keywords`、`source_title`、`source_organization`、`source_url`、`source_date`、`updated_at`、`reviewed_at`、`status`、`risk_level`、`suggested_questions`。

固定代码：

- `domain`：`student-aid`、`education-growth`、`agriculture`、`community`、`employment`、`local`、`shared`、`youth`。
- `audiences`：`student`、`parent`、`rural-youth`、`farmer`、`villager`。
- `status`：`draft`、`published`、`archived`。
- `risk_level`：`normal`、`verify-officially`、`high`。

## 文档状态

- `draft`：内容或来源尚待指导老师、项目内容负责人或官方资料复核，不进入可用知识集合。
- `published`：已完成结构、安全边界和可复述内容核对，允许进入可用知识集合；`risk_level` 为 `verify-officially` 或 `high` 时，回答仍须提示官方核验。
- `archived`：已过期或被新版本替代，只保留追溯，不进入可用知识集合。

## 如何新增知识文件

1. 从政府部门、学校或其他权威机构的可核验资料整理内容。
2. 在对应领域创建小写英文、连字符命名的 Markdown 文件。
3. 在文件顶部写明适用对象、地域、更新时间、来源状态和免责声明。
4. 在 `catalog.json` 增加唯一记录，填写真实来源；不知道的网址或日期必须留空，不得猜测。
5. 新文档先设为 `draft`。
6. 运行知识库测试和统计检查。
7. 由指导老师或项目指定的内容审核负责人完成原文、来源、时效和风险提示审核后，才可改为 `published`。

开发人员只能完成结构校验和迁移核对，不能因为技术测试需要擅自虚构来源或把未审核内容发布。

## 来源与审核要求

- `source_url` 必须来自已有可靠材料，不允许模型或开发者猜测。
- 政策金额、条件、期限、材料和办理地点不得自行更新。
- 来源没有发布日期时，`source_date` 保留空字符串。
- 高风险或可能变化的内容使用 `verify-officially` 或 `high`，正文继续提示以官方最新通知为准。
- 文档发生变化后应更新 `updated_at`；完成内容复核后填写 `reviewed_at`。

## 第三批次迁移说明

- 五份 PDF 均为图片型资料，已逐页渲染核对后迁移。
- 涉及金额、资格、未来年份、地方项目数字、电话或办理地点且缺少原始政策页面的内容保持 `draft`。
- `published` 条目只保留可安全复述的流程、核验方法、经验建议和风险边界。
- 每份农业文档均包含广东/惠州适用范围、农技诊断边界和禁止直接推荐具体农药剂量的提醒。
- 本批次没有修改 `/api/chat`、DeepSeek 参数、前端或部署配置。是否使用知识检索仍由项目已有的 `USE_KNOWLEDGE_RETRIEVAL` 灰度开关决定。
