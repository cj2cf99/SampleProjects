# 月下秘仪 · Nocturne Tarot

一间烛光占卜屋，一副完整的 78 张塔罗牌。薇拉会在窗边擦灯和理牌，轻叩桌铃，她才转身与你交谈。选姻缘、前路或事业，从七张候选牌中抽三张，依次揭开来处、当下与下一步。每张牌自带本地正逆位牌义。全翻开后点「听薇拉解读」，她会结合本局问题与牌阵回答。

## 本机运行

在 PowerShell 执行以下两行，然后打开 [月下占卜屋](http://127.0.0.1:8786/)。

```powershell
Set-Location G:\samplePj\magiccard
.\start.ps1
```

游戏服务使用 Node.js（本机已用 Node 24 验证）。启动脚本会复用已就绪的本机服务，或启动 llama.cpp 及游戏。默认推理地址为 `http://127.0.0.1:18786/v1`。当前机器的程序位于 `.runtime/llama/llama-server.exe`，模型位于 `G:/t2t/qwen3-8b-ft-q4_k_m.gguf`。模型与推理程序独立于游戏源码。换电脑时，可通过 `LLAMA_SERVER`、`TAROT_MODEL_FILE` 指定自己的二进制文件与 GGUF 模型。

已运行兼容 Chat Completions 的推理服务时，在启动前设置 `AI_BASE_URL`（含 API 版本路径）、`AI_MODEL`，按服务需要设置 `AI_API_KEY`，再执行 `node server.mjs`。密钥仅由服务端读取。前端调用同源 `POST /api/reading`，模型服务暂不可用时仍可读牌，随后在原牌阵重试。游戏在内存中保留本局，刷新即回到窗边。

## 表演与制作

三款牌背分别有星轨、花心和林间萤光。大阿卡那和宫廷牌采用人物、动物或道具剪纸分层，数字牌按实际点数编排花色图案。翻牌才加载对应的短片，系统启用减少动态效果时显示本地静态画。所有成片已在项目内，试玩无需渲染。

- [原始需求与验收](REQUIREMENTS.md)
- [详细设计](docs/DESIGN.md)
- [占卜屋与全牌组复核](docs/reviews/SALON_REVIEW_2026-11-20.md)
