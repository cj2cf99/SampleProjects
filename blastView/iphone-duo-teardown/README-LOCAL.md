# iPhone Duo 爆炸图本地样例

双击 `dist/index.html` 即可在支持 WebGL 的浏览器里看拆解。页面默认播放，也可以暂停、拖动下方进度条或点左侧零件。模型、脚本和字体都在单个 HTML 里。

源码来自 [Brad Dunlap 的 Protomota 项目](https://github.com/protomota/experiment-iphone-duo-teardown/tree/91f5155301eae818407880e233a5ea1cd2e12ce4)。本地版移除了品牌页头、页脚和标志，并将许可证嵌入 HTML。模型参考了拆解图与维修图，部分尺寸为视觉估算。项目代码为 MIT，源自 iFixit 的拆解内容按 CC BY-NC-SA 3.0 提供。

编辑源码后，运行 `npm ci`、`npm test` 和 `npm run build`。新生成的单文件在 `teardown-out/dist/duo-live.html`。
