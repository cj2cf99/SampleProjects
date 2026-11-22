# 人鱼水阻与柔性发束版

> 头发要有顶着水流跟着身体走时候的软质材料特有的摆动感。你这个严重缺乏，你去找找相关内容看看再对头发进行再优化。

以 `WaterFlow/Mermaid_WaterFlow.blend` 为基线，重点是发束本身受水弯曲，以及这种弯曲在发中和发尾之间的传递。场景继续使用原人鱼、双束扎发和 17 秒三段动作。

## 参考与取舍

- 看了 Stella the Siren 发布的真实水下画面。向前游时长发顺着来流拖在身后，仍能分辨不同发层。用这一点安排发束收拢和展开。 [Stella 的长发人鱼实拍](https://www.youtube.com/watch?v=pVz_Zo-2vZg)
- EPFL 的水中柔性体实验对比了不同速度下的弯曲。这里借鉴随相对流速改变形状的规律，给每个导向节点单独计算阻力。 [EPFL 水流柔性体实验](https://mediaspace.epfl.ch/media/V0070%2B-%2BReconfiguring%2Bit%2Bout%3A%2Bhow%2Bflexible%2Bstructures%2Binteract%2Bwith%2Bfluid%2Bflows/0_p2rv567a/30748)
- Framestore 的调校说明强调水下头发会散开，形状仍需方便阅读。Disney Research 的论文展示了给发束模拟叠加导向的做法。这里保留两束扎发的剪影，限制发根，在模拟上控制弯曲传到发梢的先后。 [Framestore《小美人鱼》制作说明](https://www.framestore.com/work/little-mermaid) · [Disney Research HairControl](https://studios.disneyresearch.com/wp-content/uploads/2019/03/HairControl-A-Tracking-Solution-for-Directable-Hair-Simulation-Paper.pdf)

## 实现与复检

1. 第一轮使用保持骨段长度的柔性导向链，固定前两点，以节点相对水速施加横向阻力、浮力和阻尼。画面中悬停的发尖可弯曲。前游和翻转的发尾仍显偏硬，局部回弹偏快。
2. 第二轮放松弯曲约束、提高阻尼，对烘焙方向做短时平滑。单帧位移峰值降低，翻转期间发中和发尾的错开仍不够明显。
3. 第三轮增加受速度调节的分段曲率导向和发束扇开形态键。沿长度让发中先弯、发尾后扫，两侧响应错开。前进时内部发层略收拢，放缓时能散开。最终将骨骼动作和两条扇开形态键烘焙至时间轴。

同镜位抽看 58、110、233、252、277、327、389、436 和 477 帧，也取样了 217 到 297 帧的弯曲连续性。逐帧测量两段发束中轴夹角，翻转时左侧前半段的第 5–95 百分位跨度从 16.7° 增至 42.4°，末段从 30.7° 增至 44.5°。右侧分别从 15.0° 增至 16.7°、从 35.2° 增至 36.4°。两侧保留不同幅度。曲率导向用于夸张可读性，水阻为局部近似。

逐帧检查 510 帧，长发与手和前臂、躯干、服装及鱼尾的三角网格未检出相交。角色最小取景余量为 3.23%，距海床最近约 0.763 个场景单位。贴图已打包。基线工程 SHA-256 为 `D9EBAD06622DF8CF154A94DFDDCD00384EE99CBF05ECAACE663A1E300665FAFC`，新版工程为 `F57A2E3407C71AA4E88BB6293AB243B02D0BE14B2B3DACA30B415DA585DC9903`。

`Mermaid_FluidHair.mp4` 为 17 秒、1440 × 810、30 fps 的完整成片。`Mermaid_FluidHair_Comparison.mp4` 为 7.8 秒同镜位局部并排，截取翻转和悬停，用同一时刻比较受水弯曲。两支视频已通过 FFmpeg 完整解码。

## 工程与重建

查阅 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md` 及 `MermaidActions\WaterFlow\README.md`。目录中未找到独立人鱼设计备忘录。继续使用可离线编辑的单个 Blender 工程与现有烘焙流程。

```powershell
$blender = 'G:\blender\app\blender.exe'
& $blender --background --factory-startup --disable-autoexec ..\WaterFlow\Mermaid_WaterFlow.blend --python-exit-code 9 --python .\fluid_hair.py -- .\Mermaid_FluidHair_Rebuilt.blend
& $blender --background --factory-startup --disable-autoexec --gpu-backend vulkan .\Mermaid_FluidHair_Rebuilt.blend --python-exit-code 9 --python ..\PolishedSwim\render_polish_review.py -- .\frames
```
