# Feather 写实度对照实验

## 需求与范围

> 参考这个网页上的2个视频和一个静态图，我需要你去新开一个子文件夹叫feather，然后在这个里面去用任何可以用的方法去尝试生成同样精度和效果的鸟类羽毛效果，你只用城市一个翅膀就行，反复迭代，知道你认为你做不到为止或者已经超越参考为止。
>
> 交给你，自己实验，停止条件不变

本次延续单翼实验。质量判断以 Fab 三项公开预览为参照，首先用固定机位和灯光比较原版凹凸、透明羽缘及曲线绒羽。确认有改善后再扩到整翼，检查翼背、翼腹、收拢及拍动。最多复核三轮。模型和源图用于本地实验，正式采用需在目标项目适配并独立验证。 [Fab 参考](https://www.fab.com/listings/e4665ec7-c6ca-4cac-bf9e-02d20b8acf48)

查阅 `C:/Users/asura/.codex/AGENTS.md`、`C:/Users/asura/.claude/CLAUDE.md`、`G:/selftool/resourceforlater/docs/FRAMEWORK_PREFERENCES.md` 和上一版的实验记录。按最简原则，在原有场景和关键帧基础上替换羽缘表示和局部梳理。项目沿用上一版在规则及索引中的查阅结果，独立的全局开发设计备忘录未找到，本实验没有单独项目备忘录。 [上一版记录](../README.md)

## 结果

- [固定镜头前后对照](comparison.png) · [最终翼根原图](shoulder.png)
- [整翼](dorsal.png) · [羽毛近景](macro.png) · [收拢](folded.png) · [翼腹](ventral.png)
- [展收与拍动](motion.mp4) · [可编辑场景](warbler-wing-realism.blend) · [生成脚本](build_realism.py)

新场景包含 342 枚曲面羽片和 23,098 条可编辑绒羽曲线。在羽片图集中打包每根羽枝的色泽、凹凸、磨损和透明轮廓。飞羽、覆羽、松散短羽使用不同模板。展开、收拢和拍动沿用相同的肩、肘、腕动作及飞羽形态键。模型贴图由脚本生成，Fab/Sketchfab 的公开预览只用于目视比较。 [公开模型信息](https://sketchfab.com/3d-models/black-and-white-warbler-ab92088661c3469a9ac651f72ff4dc7a) [羽毛分层和羽枝簇](https://www.sidefx.com/docs/houdini/feathers/randomizing.html)

## 三轮复核

| 轮次 | 发现与修正 | 固定机位画面 |
| --- | --- | --- |
| 1 | 单独测试透明遮罩与不等距羽枝。羽缘开始出现细缺口，连续的压纹感减轻，仍能看到翼根布置太规则和少量露底。 | [基线](01-baseline.png) · [透明羽缘](02-cards.png) |
| 2 | 增加短覆羽和曲线短绒，改变部分白羽尖深浅和形状。翼根露底减轻，表面却出现亮色枝杈状绒羽。 | [曲线短绒试样](03-groom.png) |
| 3 | 压低并减细绒羽，把细丝留在羽缘和搭接缝内。补了翼根内侧的过渡羽，收紧长飞羽羽缘。翼腹覆羽的白尖按羽片自身的底色确定，调整了下覆羽的叠放深度。 | [最终翼根](shoulder.png) · [最终翼腹](ventral.png) |

透明羽缘和翼根过渡比基线更自然，极近景仍能辨认出少量重复纹理，浅色翼带仍有程序化的色斑形状，翼腹局部还有覆羽相交。Fab 预览以整鸟收翼为主，无法按同一展翼姿态对照。对证据所及的整体写实度，三轮结束时未判断达到或超过参考。观感待用户确认。

## 本地重建

在 `G:\samplePj\feather\realism` 运行 Blender 5.2.4。脚本读取上一级目录的 `warbler-wing.blend` 作为基线。该基线场景的 SHA-256 为 `31D1A5DF668A972927A18CBAE3B5242AD20A9F74FA0DBAC2784A912C613AD04F`。

```powershell
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_realism.py -- --stage wing
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_realism.py -- --stage motion
& 'G:\blender\app\blender.exe' -b --factory-startup warbler-wing-realism.blend --python-exit-code 7 -P verify_realism.py
```

`--stage cards` 和 `--stage groom` 可分别运行局部卡片和绒羽预览。保存的首轮、二轮图片是当时的材质结果，当前源码带有第三轮的图集修订。GPU 渲染通过 Cycles OptiX 执行，`--cpu` 可改用 CPU。

最终验证使用 Blender 5.2.4 和 RTX 4060 Laptop GPU。重开场景确认 342 枚羽片、23,098 条曲线和内嵌透明度图集。比对图及八张独立渲染经检查。动画为 960 × 614、24 fps、90 帧，几何投影最小留边 6.14%。重新解码并目视检查第 25 帧和第 55 帧。 [验证日志](verification.log) · [展开帧](proof-frame-25.png) · [下拍帧](proof-frame-55.png)

本轮生成脚本的 SHA-256 为 `69EA0D6D85C40E389A6068FC57CC9B8E4AB8F9DAD39113DC2920A4A44E2597C8`。
