# 人鱼配色与泳姿版

> 这角色缺染色，先把颜色染了，然后去参考人类游泳和鱼类游泳动作分别取针对修改上下半身的动作。

从上一版 `Mermaid_swim.blend` 开始，先检查配色，再调三段泳姿。沿用用户下载的模型、骨架、三段路线和时长。暖珊瑚色头发从发根到发梢渐浅，青绿色鱼鳞向尾部过渡到蓝色和淡紫鳍缘。耳鳍补青紫色，上衣为紫色金边。原贴图用于保留五官、发束和皮肤纹理，重复鳞纹来自鱼尾静止形状上的坐标。

## 动作

| 时间 | 上身 | 腰部及以下 |
| --- | --- | --- |
| 0:00–0:05.6 灵活游泳 | 双臂交替前伸、抬肘抱水、将水推过髋侧，再转掌回臂。肩部随划水轻微换边。 | 沿原 S 形路线下潜再抬升。摆动从腰传向尾端，向后逐步放大。沿路线较快时摆尾节拍更快。 |
| 0:05.6–0:11.6 转圈前进 | 入转时收拢手臂，转动中双手前伸成流线，出转时缓慢打开手。 | 绕螺旋路线前进一圈。摆动沿鱼尾中心线逐段传播，尾鳍延后弯曲并收展。 |
| 0:11.6–0:17.0 悬停 | 上身保持直立，手肘微弯，手掌在胸腹前小幅内外划水。 | 腰部保持在原位置附近。尾部按较慢节拍摆动，保留明显的尾鳍踩水动作。 |

三段共 510 帧、30 fps。肘腕按原角色的臂长求解。鱼尾按各骨段长度保留由腰到尾鳍的相位差，摆幅集中在后段。参考鱼类躯干和尾鳍的推进方式，按模型宽尾鳍的形状安排上下摆动与侧向修正。手掌和尾鳍动作均已烘焙进 Blender 时间轴。

## 参考

- 抬肘抱水、后推至髋侧以及水下回臂取自美国大师游泳协会的自由泳练习说明。[USMS 自由泳水下划水](https://www.usms.org/fitness-and-training/articles-and-videos/articles/how-to-get-more-from-your-freestyle-pull)
- 直立稳定、双手在身前内外划水参考 Swim England 的踩水示范。[Swim England 踩水指南](https://www.swimming.org/assets/charter-resources-operators/guidance-documents/water-safety.pdf)
- 由腰到尾端的波动相位和后段摆幅取自鱼类游动数据。尾鳍收展借鉴鱼类加速及滑行研究。[鱼类波动游泳运动学](https://pubmed.ncbi.nlm.nih.gov/34853171/) · [鱼类尾鳍在加速和制动时的变化](https://pubmed.ncbi.nlm.nih.gov/19112147/)

## 工程与重建

`Mermaid_ColoredSwim.blend` 是可编辑工程，贴图已经打包。三段动作在时间轴上有镜头标记，`Mermaid_ColoredSwim.mp4` 是 17 秒无声预览。本版使用骨骼约束和形态键表现泳姿。

逐帧检查了全片 510 帧，手、鱼尾及尾鳍在画面内，最低点与海床保留约 0.75 个场景单位的间距。转圈中段的腕间距中位数从初版调整时的 0.28 收拢到 0.064。测量骨架确认三个片段的摆幅均自腰向尾端逐步增大，悬停时两侧手腕保持在腹部前方。

本地单人试作参考全局 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md`，沿用现成工程和骨架。项目说明及目录中未找到独立的人鱼设计备忘录。

从本目录分别执行这三行可重做颜色、动作和 PNG 帧。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --gpu-backend vulkan ..\Mermaid_swim.blend --python-exit-code 9 --python .\recolor_mermaid.py -- .\rebuilt
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --gpu-backend vulkan .\rebuilt\Mermaid_color.blend --python-exit-code 9 --python .\swim_reference.py -- .\rebuilt
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --gpu-backend vulkan .\rebuilt\Mermaid_stroke_study.blend --python-exit-code 9 --python ..\render_mermaid.py -- .\frames
```
