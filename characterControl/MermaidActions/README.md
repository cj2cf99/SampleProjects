# Character Control 人鱼动作试作

> 我刚才下载了个人鱼模型，你试试看让她做以下动作1.高零活动的有用动作 2.在水里转圈前进 3.悬停，但是下半身鱼尾摆动踩水

第一项按“灵活的游泳动作”处理。以 Downloads 中的 `Mermaid_Anime_32cf34e3-ab0b-463c-9311-d60c5f723aac.blend` 为源模型，沿用它自带的 Rigify 鱼尾、手臂和发束控制。模型的源文件留在 Downloads，项目使用已打包的贴图。

## 三段动作

| 预览时间 | Blender 帧 | 动作 |
| --- | --- | --- |
| 0:00–0:05.6 | 1–168 | 灵活游泳。沿 S 形路径下潜再抬升，交替划手、侧倾和摆尾。 |
| 0:05.6–0:11.6 | 169–348 | 转圈前进。以平滑的螺旋线前进，绕轴一整圈，收展手臂控制姿态。 |
| 0:11.6–0:17.0 | 349–510 | 踩水悬停。上身在原位附近保持平衡，手臂轻划，五段鱼尾依次摆动，尾鳍随动弯曲。 |

`Mermaid_swim.blend` 是可编辑的动画工程。三段镜头在时间轴上有标记，`Mermaid_preview.mp4` 是无声预览，30 fps，共 510 帧。

## 处理与验证

首版的鱼尾和发束在子骨上重复叠加了上节旋转。针对动画副本调整了对应约束，避免踩水时尾鳍卷到腰部附近。重新调整了悬停手肘和鱼尾摆幅。首轮镜头抽查有一次急转出界，随后放宽了急游段取景。

动作由骨架与尾鳍形态键合成。水下灯光、光束和海床光纹用于帮助观察不同方向的游动。尾巴、尾鳍和发束使用烘焙的动画驱动。

复核片段的起止帧、全身尺寸和镜头。以原模型的场景单位测量，螺旋段向前移动 4.68，鱼尾跟随身体绕行一整圈。悬停时腰部在三个轴上的峰峰位移均小于 0.08，鱼尾端在身体局部坐标里的横向峰峰位移约 0.55。检查了全片 510 帧，角色顶点均在镜头内，离海床最小距离约为 0.85 个场景单位。

设计参考了 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md` 的本地单人和最简原则，直接使用素材已有的控制骨骼。`characterControl` 内未找到针对人鱼动作的设计备忘录。

从项目目录运行以下命令可通过 Downloads 里的原始模型另建同一组动作。

```powershell
$source = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads\Mermaid_Anime_32cf34e3-ab0b-463c-9311-d60c5f723aac.blend'
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec $source --python-exit-code 9 --python .\animate_mermaid.py -- .\rebuilt
```

`render_mermaid.py` 可用于全片重渲。Vulkan 后端已在本机验证。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --gpu-backend vulkan .\Mermaid_swim.blend --python-exit-code 9 --python .\render_mermaid.py -- .\frames
```
