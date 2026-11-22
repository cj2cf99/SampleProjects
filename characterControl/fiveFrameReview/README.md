# Character Control 五帧校对版

> 动作精准度不足，请以5帧一组进行校对，现在明显丢失了很多动作的细节导致动作有点像是偷懒的新手做不标准，流畅度也不够，另外头发和布料应当是轻盈缺少弹性，柔软的轻盈材质，右边看起来弹性过头了，左边没动静。

继续使用原来的两个二次元角色，各自保留身高、步幅和臂展。按原片的时序还原篮球、顶肩、转身和后续舞步。

## 播放

- `preview.mp4` 是双角色无声预览，左边为 NOTPB，右边为 Mint。25 fps，894 帧，35.76 秒。
- `characterControl.blend` 含可编辑动作、烘焙的轻质头发和衣料动画、篮球和打包贴图。打开 Blender 工程即可回放。
- 原片 18.76 秒对应预览 0 秒。可重点看约 19.2 秒手臂翻落、21.8 秒手腕回收、24.5 秒抬手过眉、29 秒横扫接举臂。[原版参考](https://www.bilibili.com/video/BV15b41157i4/)

## 每五帧的校对

- `five_frame_review.csv` 按原速把全段分成 179 组。前 178 组各 5 帧，最后一组 4 帧。表中列出原片时间、工程帧号、参与比较的方向数量，以及上一版和这一版可见肩线、躯干和肢体的二维投影方向角误差。
- 每帧按可见度和画面长度筛选可比较的关节。出画、严重遮挡和过度缩短的肢体不会计入误差。逐帧检查误差较大及重要动作的画面，人工补记了轮廓清晰处的肘腕位置。相同的补记也用于旧版对照。人工补记见 `manual_landmarks.json`。
- 新版分别跟随上臂和前臂方向，并在可见时采用额外提取的掌向与指节弯曲。重新处理了 38.00 秒推手、40.5 秒抬手回收、43.2 秒开始的抬手过眉，以及 47.7 秒之后的横扫。模糊或出画的动作仍需估算，尤其是后半段脚步。
- 以相同的 6845 个可见方向复测。左侧的手臂方向均差由 10.91° 降至 2.04°，Mint 由 9.38° 降至 2.19°。快速变化帧的相邻帧转角差分别由 14.94° 降至 4.78°、由 15.20° 降至 4.97°。这些数值衡量的是同一帧、同一可见方向的二维对照。
- 宽幅手势有短段平缓的横向镜头跟随，避免 Mint 的手伸出右边缘。

## 材质动态

两人的发束和布料都改为带重量偏置的阻尼跟随。Mint 的发束和丝带限制了摆动角，衣摆更快落稳。左侧角色的两侧发梢和两边裙缘分别跟随头部和髋部的起停，发根和腰口使用原蒙皮约束。在相同姿势开启和关闭物理的对照渲染中，转身和抬腿时均可见发梢及裙边的位移。衣摆采用加权变形，身体接触采用简化模型。

## 重建

本试作按本地单人使用和最简设计处理，参考了 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md`。项目目录未找到独立的设计备忘录。

从项目目录运行下列命令会读取 Downloads 中的原始 GLB 和本版 `motion.json`，生成新的工程文件。使用同目录的 `render_take.py` 可重渲预览帧。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 9 --python .\build_scene.py -- refine .\rebuilt
```

- 左侧模型由 NOTPB 上传，原文件标为 CC BY 4.0。[模型来源](https://sketchfab.com/3d-models/cute-anime-girl-fully-rigged-3d-model-ef055d864b9d426691f973fb60af0457)
- Mint 由 Jun Hungry 上传，原文件标为 CC BY 4.0。[模型来源](https://sketchfab.com/3d-models/mint-swimsuit-animated-neverness-to-everness-6dbe3e3dc6704a36bb3acef80b0bc5e4)
