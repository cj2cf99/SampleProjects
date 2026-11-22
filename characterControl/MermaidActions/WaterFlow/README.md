# 人鱼水下发束与动作修订

> 头发太僵硬了，动作再自然一些

以 `PolishedSwim/Mermaid_Polished.blend` 为基线。三段仍是下潜抬升、转圈前进和摆尾悬停。修订集中在发束、头胸引导和悬停托水。

## 动作

- 两侧长发分别读取头部的方向和位移历史。发根固定在绑发处，发中和发梢逐级延后跟随。转身时发梢先留在旧方向，再受阻尼慢慢跟上。加了小幅上浮和横漂，让悬停时也能看到两束发尾错开浮动。
- 刘海用两条形态键做小幅侧漂和上浮，发际线保持固定。长发仍用原有八节骨骼，烘焙过程维持原骨长。背部附近留出间隙。
- 下潜和抬升各有小幅的头胸预转。悬停改为交错托水，手掌在拨水和回收之间转动，手指随着托水放松或舒展。

分段关键帧检查包括 110 帧的抬升、233 到 277 帧的翻转、389 到 477 帧的悬停。按头部坐标系测量发梢运动，翻转时左右发梢的活动范围从 0.064 和 0.087 增至 0.239 和 0.299 个场景单位，悬停时则从 0.062 和 0.048 增至 0.197 和 0.137。这里的范围是各轴峰峰值组成的包围盒对角线长度。发束用骨骼运动和阻尼近似水中阻力，刘海使用形态键。

## 验证

检查全部 510 帧的取景、轨迹和网格相交。三段保留完整前游、360° 翻转和摆尾悬停，角色最小取景余量为 3.23%。按三角网格检测，长发未穿过手和前臂、躯干、上衣或鱼尾。贴图保持打包。基线工程 SHA-256 为 `9DF96C39B1BDE7425560CD9C614CC23CEF19F5CA76AB36F8AD236C21FC1D0481`，新版为 `D9EBAD06622DF8CF154A94DFDDCD00384EE99CBF05ECAACE663A1E300665FAFC`。

`Mermaid_WaterFlow.mp4` 为 17 秒、1440 × 810、30 fps、510 帧的 H.264 视频，已通过 FFmpeg 完整解码。

## 工程与重建

动画烘焙在 `Mermaid_WaterFlow.blend`，在 Blender 中可编辑。影片沿用原来的三个镜头和 17 秒时长。模型、灯光及渲染工作流以现有工程为基础。查阅了 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md` 以及 `MermaidActions\PolishedSwim\README.md`，项目目录未找到独立设计备忘录。

从本目录运行以下命令可以重建工程和 PNG 序列。

```powershell
$blender = 'G:\blender\app\blender.exe'
& $blender --background --factory-startup --disable-autoexec ..\PolishedSwim\Mermaid_Polished.blend --python-exit-code 9 --python .\waterflow_mermaid.py -- .\Mermaid_WaterFlow_Rebuilt.blend
& $blender --background --factory-startup --disable-autoexec --gpu-backend vulkan .\Mermaid_WaterFlow_Rebuilt.blend --python-exit-code 9 --python ..\PolishedSwim\render_polish_review.py -- .\frames
```
