# AI 语音维修下单前端

技术栈：

- Vue3
- Vite
- Tailwind CSS

## 启动

```bash
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://localhost:5173
```

开发环境下，`/api` 会代理到：

```text
http://localhost:8000
```

## 页面模块

- 麦克风按钮：调用浏览器语音识别能力。
- 对话区：展示用户和 AI 的多轮对话。
- 语音动画：监听时显示动态声波。
- 预下单卡片：从用户输入中轻量预览房号、商品、故障、区域、紧急度。
- 历史对话：展示最近维修会话入口。

## 注意

浏览器语音识别依赖 Web Speech API，不同浏览器支持程度不同。Chrome 系浏览器通常支持较好。
