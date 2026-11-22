# Character Control 动作试作

当前留档采用五帧校对版。项目根目录内的工程是首版。[当前版本说明](fiveFrameReview/README.md) · [三版复刻记录](MOTION_RECREATION_LOG.md)

用 Downloads 里的两个二次元角色，在本地重演蔡徐坤《只因你太美》片段。目标是尽量跟上原片的动作、节奏、运球和表情。按最后一条要求使用卡通渲染，这轮关闭头发和衣服的物理模拟。

## 打开

- `preview.mp4` 是左右并排的无声渲染。左侧是 NOTPB 的原创角色，右侧是 Mint。时长 35.76 秒，25 fps。
- `characterControl.blend` 是可编辑项目，骨架、动画、两颗篮球和贴图都在文件里。用 Blender 打开后按空格播放，或用时间轴逐帧检查。项目使用 Eevee。
- `motion.json` 保留原片时间码、姿势、篮球中心和可辨认的面部轨迹。它与 `build_scene.py` 可用来重建项目。

参考采用原片 18.76 至 54.52 秒，覆盖运球、抛球、背身顶肩和后续舞步。预览第 0 秒对应原片 18.76 秒，时间未拉伸。项目里有关键动作的时间轴标记。[原版参考片段](https://www.bilibili.com/video/BV15b41157i4/)

## 本轮结果

第一版逐帧重定向时发现 Mint 悬空，个别持球姿势出现手离球。第二版用角色蒙皮网格校准脚底，按原片可见的反弹点调整球的高度，并把接触帧的球贴回手掌。全片抽检发现转身和抬腿还存在局部穿地，针对这些段落修正了 49 帧并重新渲染。左侧角色原贴图有眼睛和肤色，服装和头发主要是浅灰，本试作给这两块加了蓝紫配色。

Mint 使用面部骨骼跟随辨认到的开口、嘴角和眨眼。左侧角色的原始模型没有面部骨骼或表情形态键，表演由头颈姿态表现。原片后半段有脚出画，背身与模糊帧也有追踪误差，相关姿势由邻帧和骨骼轨迹估计。

## 模型与重建

- 左侧模型由 NOTPB 上传，原文件标为 CC BY 4.0。[模型来源](https://sketchfab.com/3d-models/cute-anime-girl-fully-rigged-3d-model-ef055d864b9d426691f973fb60af0457)
- 右侧模型由 Jun Hungry 上传，原文件标为 CC BY 4.0。试作把上传文件中独立陈列的三组配件隐藏。[模型来源](https://sketchfab.com/3d-models/mint-swimsuit-animated-neverness-to-everness-6dbe3e3dc6704a36bb3acef80b0bc5e4)

从本目录运行下列 PowerShell 命令会读取 Downloads 中的原始 GLB，向 `rebuilt` 写入新项目和抽帧。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 9 --python .\build_scene.py -- refine .\rebuilt
```

需要重新渲染时，可在 Blender 用「渲染动画」，或从项目目录运行以下命令把帧写到 `frames`。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec .\characterControl.blend --python-exit-code 9 --python .\render_take.py -- .\frames
```
