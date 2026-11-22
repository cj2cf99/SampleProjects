# 人鱼泳姿五轮优化

> 对动画的流畅度和自然度，模型的美化进行5轮优化

从 `GracefulSwim/Mermaid_GracefulSwim.blend` 开始，保留同一人鱼和三段表演。前游包含下潜和抬升，转圈边翻转边前进，最后摆尾悬停。持续使用原项目参考的人鱼表演节奏，上半身的动作轻，尾部负责推进。三段镜头分别从 0、5.6、11.6 秒开始。

## 逐轮调整

| 轮次 | 发现与处理 | 核对画面 |
| --- | --- | --- |
| 1 | 原版尾部后段有短促的甩动，前游身体带有规律的快速滚转。沿鱼尾重新分配弯曲，尾鳍延后响应，转圈从较慢入转到中段提速，再缓慢放开。 | 58、252、389 帧的前游、翻转、悬停形态 |
| 2 | 起游时肘部转折偏快。让手腕缓一些到达引导位置，稳定肘部的弯曲方向，叠加头胸领动和手指收放。 | 58、110、252、389、451 帧的下潜、抬升、转向和悬停手势 |
| 3 | 发束跟随转身的滞后不足，原眼睛缺少瞳孔层次。让发梢比发根晚响应，给原虹膜网格加瞳孔与眼神光，加入微移的视线和几次短眨眼。 | 252 帧的翻转发束，389、408 帧的睁眼与眨眼 |
| 4 | 皮肤、尾鳍和服装的光泽差别偏小。调整渐变和局部粗糙度，给鱼尾加浅鳞片凹凸和鳍条纹理，保留长发的珊瑚色，并让衣缘有较克制的金属光。 | 252、389 帧的鳍面、服装边缘及轮廓 |
| 5 | 水下背景偏平、前两段人物在画面中偏小。重设跟拍和取景，降低背景及海床亮度，补偏冷的轮廓光和较暖的主光。最终原生分辨率为 1440 × 810。 | 58、110、252、389、451 帧的构图与材质对照 |

## 验证

基线 SHA-256 为 `C6B15EA6C46D023DF28AB4C9C703DBD4009F9AE0333973632253FE20269718B1`。

在 Blender 中按 30 fps 评估关节局部四元数。排除两次剪切，前臂最大相邻帧转角从 12.42° 降至 4.78°，第 95 百分位从 4.45° 降至 3.10°。五节鱼尾骨的最大相邻帧转角从 35.90° 降至 18.77°，第 95 百分位从 13.03° 降至 7.18°。第三轮抽查了 78 帧。第五轮对全片按三角网格复检，手与前臂未与躯干、上衣、鱼尾或长发网格相交。眨眼抽查在 408、481 帧。

逐帧核对了 510 帧的取景，角色完整入镜，最小画面边距为 3.23%，与海床最近约 0.763 个场景单位。前游纵向起伏跨度 1.02 个场景单位，前进转圈一整圈，悬停时腰部在每轴的峰峰值均小于 0.08 个场景单位。

成片 `Mermaid_Polished.mp4` 经 FFmpeg 完整解码校验，规格为 H.264、1440 × 810、30 fps、510 帧、17 秒。`Mermaid_BeforeAfter.jpg` 按三段各选一帧对照构图和模型呈现。最终工程 SHA-256 为 `9DF96C39B1BDE7425560CD9C614CC23CEF19F5CA76AB36F8AD236C21FC1D0481`。视觉效果待用户确认。

发束使用骨骼动画和滞后响应，三段沿用硬切。贴图打包在 Blender 工程内，鳞片和鳍条纹理使用保存在模型中的休止位置属性。工程可本地编辑和渲染。

## 重建

方案沿用原项目的骨架与本地 Blender 工作流。查阅了 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md` 和原项目 `MermaidActions\GracefulSwim\README.md`，项目目录未找到独立设计备忘录。复用既有工程和动作脚本，资产、骨架、三段动作及影片时长按原范围保留。

在本目录用 Blender 5.2.4 运行下列命令可重新生成五个阶段及 PNG 序列。

```powershell
$blender = 'G:\blender\app\blender.exe'
$inputScene = '..\GracefulSwim\Mermaid_GracefulSwim.blend'
foreach ($stage in 1..5) {
    $scene = ".\round$stage.blend"
    & $blender --background --factory-startup --disable-autoexec $inputScene --python-exit-code 9 --python .\polish_mermaid.py -- $stage $scene
    if ($LASTEXITCODE -ne 0) { throw "Blender pass $stage failed" }
    $inputScene = $scene
}
& $blender --background --factory-startup --disable-autoexec --gpu-backend vulkan $inputScene --python-exit-code 9 --python .\render_polish_review.py -- .\frames
```
