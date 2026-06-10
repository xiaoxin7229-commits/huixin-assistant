# 惠心小助 AI资助政策问答助手

## 项目介绍

惠心小助是惠州学院“惠心筑梦实践队”用于广东省 2026 年“国家资助和助学贷款政策下乡行”活动的轻量级 AI 问答智能体 MVP。项目面向学生、家长、经济困难家庭、社区群众和基层工作人员，帮助大家用通俗方式了解国家资助政策、生源地信用助学贷款、绿色通道、国家助学金、勤工助学、诚信还款等内容。

本项目不是政府官方系统，只作为政策宣传、科普和咨询辅助工具。具体办理条件、材料、流程、时间、贷款额度等，以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准。

## 文件结构

```text
huixin-assistant/
├─ app.py
├─ requirements.txt
├─ .env.example
├─ README.md
├─ policy.md
├─ qr_helper.md
├─ Procfile
├─ render.yaml
├─ .gitignore
├─ templates/
│  └─ index.html
└─ static/
   ├─ style.css
   └─ script.js
```

## 本地安装步骤

Windows：

```bat
cd huixin-assistant
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

macOS / Linux：

```bash
cd huixin-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

运行后访问：

```text
http://127.0.0.1:5000
```

## 如何配置 .env

复制 `.env.example` 为 `.env` 后，填写 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=请填写你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
FLASK_DEBUG=0
```

注意：`.env` 已被 `.gitignore` 忽略，不要上传到公开仓库。

## 如何运行项目

确保虚拟环境已激活，并且依赖已安装：

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

接口地址：

```text
POST /api/chat
```

请求示例：

```json
{
  "message": "助学贷款是不是高利贷？"
}
```

响应示例：

```json
{
  "answer": "AI回答"
}
```

## 如何修改 policy.md

`policy.md` 是项目的资助政策知识库。可以直接用文本编辑器修改：

1. 添加新的政策说明或常见问答。
2. 避免写“保证通过”“一定能申请成功”等绝对承诺。
3. 涉及条件、材料、额度、时间、办理地点时，写明“以当地学生资助管理中心、国家开发银行学生在线系统和学校最新通知为准”。
4. 修改后重启 Flask 服务，让后端读取最新内容。

## 如何生成二维码用于手机访问

公网部署后，把 Render 生成的网址转换成二维码即可。

步骤：

1. 获得公网地址，例如 `https://huixin-assistant.onrender.com`。
2. 打开可信二维码生成工具。
3. 输入公网地址并生成二维码。
4. 下载二维码图片，用于海报、展板、PPT 或宣传单。

本地测试时，`http://127.0.0.1:5000` 只能在电脑本机访问。手机扫码访问本地服务，需要电脑和手机在同一 Wi-Fi 下，并使用电脑局域网 IP，例如：

```text
http://192.168.1.8:5000
```

更多说明见 `qr_helper.md`。

## Render 公网部署步骤

1. 把 `huixin-assistant` 项目上传到 GitHub 仓库。
2. 登录 Render，选择 New Web Service。
3. 连接 GitHub 仓库。
4. Runtime 选择 Python。
5. Build Command 填写：

```bash
pip install -r requirements.txt
```

6. Start Command 填写：

```bash
gunicorn app:app
```

7. 在 Render 的 Environment Variables 中添加：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

8. 点击 Deploy，等待部署完成。
9. 使用 Render 提供的公网 URL 访问网页，并生成二维码。

本项目也提供 `render.yaml`，可用于 Render Blueprint 部署。

## 常见问题排查

### 页面打不开怎么办？

先确认 Flask 是否正在运行，终端是否显示 `Running on http://127.0.0.1:5000`。如果端口被占用，可以关闭其他占用 5000 端口的程序，或设置 `PORT` 环境变量后重新运行。

### DeepSeek API Key 没配置怎么办？

后端会返回：“当前问答服务还没有配置 DeepSeek API Key，请管理员在 .env 文件中填写密钥后重启服务。”请检查 `.env` 是否存在，且 `DEEPSEEK_API_KEY` 是否已填写。

### 手机扫码打不开怎么办？

如果二维码内容是 `http://127.0.0.1:5000`，手机通常打不开，因为这是电脑本机地址。现场使用建议部署到 Render，并用 Render 公网地址生成二维码。本地测试则需要电脑和手机在同一 Wi-Fi 下，使用电脑局域网 IP。

### Render 部署失败怎么办？

检查 `requirements.txt` 是否包含 Flask、openai、python-dotenv、gunicorn；检查 Start Command 是否为 `gunicorn app:app`；检查项目根目录是否就是包含 `app.py` 的目录；查看 Render Logs 中的具体错误信息。

### API 调用失败怎么办？

检查 DeepSeek API Key 是否正确、账户是否可用、模型名是否正确、网络是否正常。页面会显示友好提示，不会暴露后端错误。现场急需咨询时，请联系学校老师、县级学生资助管理中心或现场工作人员。

## 安全提醒

- 不要把 API Key 上传到公开仓库。
- 不要上传 `.env`。
- AI 回答必须经过人工审核。
- 项目不代替官方资格认定。
- 不收集用户敏感信息。
