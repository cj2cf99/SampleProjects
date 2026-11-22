# Feather · 黑白森莺单翼实验

这是 SampleProjects 里的本地视觉实验。模型、动画和材质用于验证做法。正式项目采用相关思路时，需要在目标项目重新实现或适配，并独立验证。

## 实验归档

**本路线于 2026-11-19（JST）暂告一段落。** 目标是用一只翅膀逼近 Fab 两段视频和一张静态图里的羽毛观感。现有路线经过多版迭代，整体拟真度仍明显低于参考。用户决定暂时停止，待发现其他路线再继续。

| 阶段 | 试验过程与结论 | 对照证据 |
| --- | --- | --- |
| 初版程序化建模 | 用曲面羽片、实体羽轴、局部羽枝和方向性材质搭出翼背、翼腹及展收动作。可分辨飞羽和覆羽层次，羽枝过于规则，翼根过渡偏硬。 | [收翼](renders/folded.png) · [展收与拍动](renders/motion.mp4) · [初版各轮复核](#初版三轮复核) |
| 透明羽缘与曲线绒羽 | 在固定机位依次测试透明遮罩、不等距羽枝、翼根短覆羽与曲线绒羽。细碎羽缘和翼根过渡有改善，极近景仍有重复纹理，翼腹有局部交叠。 | [前后对照](realism/comparison.png) · [实验记录](realism/README.md) |
| 标本比例、实拍贴图与散射 | 按黑白森莺标本调整收翼比例与覆羽叠放，轮廓和两道白翼带改善最明显。公有领域照片补充了羽缘与羽枝细节，图块复用仍会产生重复。Blender 散射近似让单羽在背光下更透，棚拍变化很小。本机缺少论文原版的 Mitsuba 0.6 插件构建环境，原版未能运行。 | [整翼](specimen-study/renders/optics-whole.png) · [同机位材质对照](specimen-study/renders/wing-comparison.png) · [单羽换灯对照](specimen-study/renders/optics-comparison.png) · [实验记录](specimen-study/README.md) |

最终收翼近景仍有重复缺口、规则条纹和短羽的切片感。同种标本的颜色、法线和透光缺少实测。最后一版只验证了静态收翼，Fab 公开预览主要是栖停姿态，动态拟真没有等价镜头可比。后续出现其他路线时，可用现有同机位整翼、覆羽近景和单羽换灯图作为对照基线。 [最终 Blender 场景](specimen-study/warbler-resting-study.blend) · [验证日志](specimen-study/verification.log)

## 原始需求

> [https://www.fab.com/listings/e4665ec7-c6ca-4cac-bf9e-02d20b8acf48](https://www.fab.com/listings/e4665ec7-c6ca-4cac-bf9e-02d20b8acf48) 参考这个网页上的2个视频和一个静态图，我需要你去新开一个子文件夹叫feather，然后在这个里面去用任何可以用的方法去尝试生成同样精度和效果的鸟类羽毛效果，你只用城市一个翅膀就行，反复迭代，知道你认为你做不到为止或者已经超越参考为止。

本次把范围理解为制作一只翅膀，并以羽毛观感为主要比较对象。物种、呈现方式和动作是实现选择。采用黑白森莺的翼上花纹，检查全翼轮廓、两层白尖覆羽、飞羽搭接、近景羽轴与羽枝，以及收拢和拍动时的连续性。

## 初版产物

| 文件 | 看什么 |
| --- | --- |
| [`warbler-wing.blend`](warbler-wing.blend) | Blender 5.2.4 场景。打开后位于第 25 帧，有 299 枚可编辑羽片和 18 枚带弯曲形态键的飞羽。完整动态取景使用 `Motion · three-quarter` 摄影机。 |
| [`dorsal.png`](renders/dorsal.png) | 展开翼背，2240 × 1440。 |
| [`macro.png`](renders/macro.png) | 白尖覆羽、羽轴、羽枝和边缘磨损，1920 × 1440。 |
| [`ventral.png`](renders/ventral.png) | 翼腹与下覆羽，1760 × 1120。 |
| [`folded.png`](renders/folded.png) | 与 Fab 栖停画面最容易比较的收拢姿态，1600 × 1200。 |
| [`motion.mp4`](renders/motion.mp4) | 收拢、展开、拍动、滑翔、收回，1200 × 768，24 fps。 |
| [`build_wing.py`](build_wing.py) | 从种子、羽区布置和参数生成场景与渲染。渲染使用 Cycles。 |

## 设计与比较依据

查看了 Fab 的两项 3D 动画预览，播放器显示时长为 8.00 秒和 7.06 秒，也查看了斜树枝上的静态图。三项画面能看到栖停或贴树时的羽片叠压、深色飞羽、浅色羽尖和破碎的纹理。展翼比例和动作没有等价镜头可直接逐帧对照。参照物种的两道白翼带采用分布在大覆羽和中覆羽羽尖的浅色斑块。翼腹配色为本次的近似设计。 [Fab 公开图库](https://www.fab.com/listings/e4665ec7-c6ca-4cac-bf9e-02d20b8acf48) [密苏里州自然保护部门物种图鉴](https://mdc.mo.gov/discover-nature/field-guide/black-white-warbler)

用一个 Blender 场景完成实验。主飞羽使用不对称双羽瓣、弯曲羽轴、局部羽缘缺口和实体游离羽枝。密排羽枝用 UV 驱动的方向性凹凸与反光表示。翼根的短绒和翼腹覆羽由各自的羽片覆盖。肩、肘、腕控制关节动作，飞羽形态键负责拍动时的弹性弯曲。这些参数及几何均独立生成，场景没有外部图像或模型依赖。

查阅 `C:/Users/asura/.codex/AGENTS.md`、`C:/Users/asura/.claude/CLAUDE.md` 和 `G:/selftool/resourceforlater/docs/FRAMEWORK_PREFERENCES.md`。采用其中的最简设计、原始需求对照和最多三轮复核原则。全局规则、项目目录和文档索引中未找到单独的全局开发设计备忘录，`feather` 为新实验目录，没有既有项目备忘录。直接迭代本地 3D 场景符合本次实验授权。主站接入、网站原型和发布流程均不适用。

## 初版三轮复核

| 轮次 | 发现及处理 | 画面证据 |
| --- | --- | --- |
| 1 | 验证展翼轮廓和主要羽区。合成节点的前后景接反，影响色彩和高光观察。转为摄影机专用环境背景，将灯光照明独立出来。 | [轮廓测试](iterations/blockout-dorsal.png) |
| 2 | 首次检查完整羽枝、羽轴及边缘细丝。整体偏灰，翼根露底，覆羽和白尖偏整齐。调整黑色素、羽轴粗细和羽端形状，加宽部分覆羽，补上翼根四行短羽。 | [整翼](iterations/field-dorsal.png) · [近景](iterations/field-macro.png) |
| 3 | 旧镜头在收拢和拍动时切到翼尖。按 90 帧的几何包围盒统一取景，为收拢姿态单设镜头。翼腹前缘还露出一段光滑底面，增加 38 枚腹侧短羽后重新渲染。 | [旧镜头收拢](iterations/pose-01.png) · [最终收拢](renders/folded.png) · [修正前翼腹](iterations/ventral-before-root-plumage.png) · [最终翼腹](renders/ventral.png) |

初版近景可以分辨覆羽和飞羽的层次、羽轴、羽枝方向和细碎羽缘。与 Fab 的栖停效果相比，羽枝纹理还有较强的规则性，翼根及白尖覆羽的过渡较硬，翼腹少量下覆羽会露出交叉尖角。密排羽枝主要由材质表达，动作采用关键帧与形态键。初版三轮结束时，未判定整体写实度达到或超越 Fab。

## 本地复现

在 `G:\samplePj\feather` 用 Blender 5.2.4 执行。场景和静帧也可以在 `.blend` 中直接查看和渲染。

```powershell
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_wing.py -- --render all
& 'G:\blender\app\blender.exe' -b --factory-startup warbler-wing.blend --python-exit-code 7 -P iterations/verify_delivery.py
```

`--render draft` 输出短耗时的展开和近景检查图，`--render poses` 输出动作检查帧，`--cpu` 强制使用 CPU。历史检查图记录了当轮结果，当前脚本使用修订后的材料与镜头。

在 Blender 5.2.4 与 RTX 4060 Laptop GPU 上执行最终构建。重开场景确认有 299 枚羽片、18 组飞羽形态键和 289,181 个基础网格面。四张渲染图尺寸通过检查。遍历 90 帧的运动摄影机，在投影包围盒中测得最小留边为 6.14%。MP4 可读取 90 帧，另解码抽查第 25 帧展开和第 55 帧下拍。 [构建日志](iterations/delivery.log) · [验证日志](iterations/verification.log) · [展开帧](iterations/encoded-frame-25.png) · [下拍帧](iterations/encoded-frame-55.png)

起点为本地空目录。生成源码的 SHA-256 为 `AC6C0D22CC092A6E299EF0F31B4FDE27CBBD7A71F14CF6F5D12786C384835072`。
