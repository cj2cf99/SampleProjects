# Character Control 比例与物理版

沿用两个 Downloads 模型和蔡徐坤原片的节奏，重做运球、抛球、转身、顶肩和后续舞步。此次按用户补充，用各角色的身高和肢体比例选择相应的步幅、下蹲和触球距离，修正 Mint 脚掌乱扭，并加入头发和服装的物理拟真效果。

## 打开

- `preview.mp4` 是左右并排的无声预览，左侧为 NOTPB 原创角色，右侧为 Mint。共 894 帧，25 fps，35.76 秒。
- `characterControl.blend` 包含可编辑的骨架动作、篮球、卡通材质、打包贴图和物理动画。打开后可播放或按时间轴标记逐段查看。物理动画已烘焙，直接打开即可播放。
- 预览第 0 秒对应参考原片 18.76 秒，动作沿用原片的帧时间。[原版参考片段](https://www.bilibili.com/video/BV15b41157i4/)

## 调整

- 左侧和 Mint 的场景身高分别约为 1.58 米和 1.70 米。这是本试作的舞台设定。按两人的大腿、小腿、上臂和前臂长度重新解算，左侧步幅较短、运球较贴身，Mint 支撑更宽。手掌与篮球在接触帧分别对齐，反弹帧贴地。
- Mint 两只鞋有不同的初始绑定角度。按鞋面网格配准校准右鞋后，脚掌朝向在舞台坐标中求解。可靠的承重段固定脚掌朝向并限制位移，转身和摆腿段平滑过渡。
- Mint 的发束和丝带使用原有骨骼。逐帧求解弹簧、阻尼、重力和近似身体碰撞。两人的衣摆及左侧模型无独立发骨的区域用蒙皮后的加权表面变形表现滞后和回弹，根部以原蒙皮为约束。
- 模型较密且衣服、身体共享蒙皮，局部遮挡和复杂布料碰撞采用近似。原片后半段常有脚出画，脚步和支撑点按可见的腰腿动作估计。Mint 有嘴部和眨眼动作，左侧模型的表情由头颈姿态表现。

## 验证与重建

比对了运球、转身、顶肩和抬腿抽帧。Mint 右脚相邻帧最大转角从 94.4° 降至 21.4°，左脚从 64.2° 降至 21.2°。在高置信度的承重段，Mint 脚尖相邻帧的水平位移中位数从 1.13 厘米降至 0.26 厘米。读取 Blender 工程确认了 894 帧时间轴、贴图打包和发束、衣摆动画随帧变化。

设计取舍参考全局 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md` 的本地单人和最简设计原则。这个试作目录未找到单独的项目设计备忘录。

从本目录运行命令可读取 Downloads 里的两个原始 GLB，并用 `motion.json` 重建项目。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 9 --python .\build_scene.py -- refine .\rebuilt
```

- 左侧模型由 NOTPB 上传，文件标为 CC BY 4.0。[模型来源](https://sketchfab.com/3d-models/cute-anime-girl-fully-rigged-3d-model-ef055d864b9d426691f973fb60af0457)
- Mint 由 Jun Hungry 上传，文件标为 CC BY 4.0。[模型来源](https://sketchfab.com/3d-models/mint-swimsuit-animated-neverness-to-everness-6dbe3e3dc6704a36bb3acef80b0bc5e4)
