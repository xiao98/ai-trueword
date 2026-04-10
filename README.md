# AI真言机

帮你判断AI信息该焦虑还是该忽略。

## 这是什么

AI领域信息爆炸，自媒体贩卖焦虑。AI真言机对每条热门AI信息做一个判定：

- **实质性突破** — 你需要了解
- **渐进改良** — 知道就行
- **营销包装** — 跳过
- **纯粹炒作** — 反向指标

每条附一段说人话的理由，30秒内完成"该不该在意"的判断。

## 运行

```bash
# 安装依赖
pip install -e ".[dev]"

# 设置API密钥
export ANTHROPIC_API_KEY=your_key

# 启动
uvicorn backend.app.main:app --reload
```

打开 http://localhost:8000

## 技术栈

- 后端：FastAPI + SQLite
- 分类引擎：Claude API
- 前端：纯HTML/CSS/JS（零依赖）
- 信息源：RSS + 手动提交
