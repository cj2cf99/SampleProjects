# 黑白森莺收翼拟真实验

> 参考这个网页上的2个视频和一个静态图……尝试生成同样精度和效果的鸟类羽毛效果……一个翅膀就行。
>
> 再找找有没有更逼近的方法，目前明显差得多，你找找拟真方案。
>
> 交给你了，都试试看。

在 SampleProjects 的 `feather` 下继续比较标本比例、实拍羽毛贴图和专用散射三条路线。选取参考预览的收翼姿态，建立一只可编辑的翼，固定场景比较三种材质。本轮交付静态局部、整翼和换灯测试，供本地实验验证。 [Fab 两段视频与静态图](https://www.fab.com/listings/e4665ec7-c6ca-4cac-bf9e-02d20b8acf48)

## 结果

- [完整收翼 2080 × 1380](renders/optics-whole.png) · [三种材质同机位近景](renders/wing-comparison.png) · [单羽侧光和背光对照](renders/optics-comparison.png)
- [程序材质整翼](renders/shape-whole.png) · [实拍贴图整翼](renders/photo-whole.png) · [最终整翼低机位背光](renders/optics-back.png)
- [可编辑 Blender 场景](warbler-resting-study.blend) · [验证日志](verification.log)

| 路线 | 实验 | 观察 |
| --- | --- | --- |
| 按标本重建 | 参考黑白森莺标本 #2584 的长飞羽、收翼轮廓和覆羽轮廓，手工设置各排长度和搭接。公开标本记录的最长初级飞羽为 61.5 mm，最长次级飞羽为 49.0 mm。成品为 61.0 和 49.0 mm，两道白翼带用独立的覆羽尖排成。 | 收翼外形和层次的改善最明显。翼根短羽堆积、羽缘阶梯和部分露底仍可见。 |
| 实拍贴图 | 从三张公有领域照片提取轮廓、羽枝对比和绒边，重投影到飞羽、带白尖覆羽和短羽。颜色、透明度、微凹凸、薄区和粗糙度变化打包进两张图集。 | 背景可透过不连续的羽缘，表面有局部羽枝细节。照片里原有的明暗仍有残留，复用图块使缺口和条纹重复。同物种的交叉偏振色彩与法线仍缺少实测。 |
| 方向性散射 | 在 Blender 用投影椭圆覆盖率近似斜视遮挡，在反射中混合两个沿不同方向的高光，并按羽瓣薄区混入透射。相同几何、镜头和贴图下，分别对比侧光和背光。 | 背光下单羽的薄处更亮，侧光和棚拍变化小。论文原版需要 Mitsuba 0.6 的指定版本和单独编译的插件，作者给出的老版依赖和遮挡工具构建链在本机缺失，原版没有成功运行。 |

标本来源只用于目视记录和尺寸核对。源照片及作者见下文。散射材质借鉴论文第 6 节的方向遮挡概念，采用着色节点近似，省去原论文的椭圆羽小枝多层散射与数值积分。渲染结果以视觉为准，未进行实物光学测量。 [Featherbase 标本 #2584](https://featherbase.info/da/specimen/2584) [物种尺寸](https://media.featherbase.info/en/species/mniotilta/varia) [论文与示例](https://graphics.unizar.es/projects/FeathersAppearance_2024/) [原版构建说明](https://github.com/juanraul8/PennaceousFeathersRendering)

## 三轮复核

1. 初始收翼已变窄。翼根基底暴露，中覆羽白尖被挡。增加短覆羽包住翼根，抬高中覆羽并减小弯拱，排出两道白翼带。 [首轮原图](renders/shape-initial.png)
2. 初次接入实拍图集后，边缘出现实拍缺口。凹凸又夸大了条纹，相邻羽片局部切割。调低凹凸，改用共同翼面和同排羽片高度顺序。 [初版实拍图](renders/photo-initial.png)
3. 补了初级和次级飞羽交界的过渡羽，并收短底层基底。减少条纹强度，完成同机位整翼与单羽换灯复测。最终仍能看到飞羽条纹和重复缺口，短羽叠层局部像切片。结合 Fab 预览，判定本轮未达到参考的拟真度。单翼只在静止收翼姿态验证，动态拟真未得到对照结果。

设计前查阅 `C:/Users/asura/.codex/AGENTS.md`、`C:/Users/asura/.claude/CLAUDE.md`、`G:/selftool/resourceforlater/docs/FRAMEWORK_PREFERENCES.md` 及 `feather` 前两轮实验记录。沿用上一级的网格、相机和渲染函数，通过同一场景比较材质；三轮依次核对轮廓、近景和换灯响应。项目规则与文档索引没有找到独立开发设计备忘录。 [最初实验](../README.md) [上轮拟真实验](../realism/README.md)

## 实拍素材

三张原图的页面均标为公有领域。三张照片来自其它或未明确标注的物种，无法代替同种标本的白斑、羽缘和透光测量。保留源图用于重建实验。

| 本地原图 | 作者和用途 |
| --- | --- |
| `sources/grey-feather.jpg` | Lynn Greyling，沿羽轴校正轮廓并提取羽缘。 [Black And White Feather On Grey](https://www.publicdomainpictures.net/en/view-image.php?image=409090&picture=black-and-white-feather-on-grey) |
| `sources/black-feather.jpg` | George Hodan，取乌鸦羽毛特写的细纹对比。 [Black Feather Close Up](https://www.publicdomainpictures.net/en/view-image.php?image=88488&picture=black-feather-close-up) |
| `sources/light-feather.jpg` | Rita Ballantyne，提取羽根附近的软绒细纹。 [B & W Feather](https://www.publicdomainpictures.net/en/view-image.php?image=1037&picture=b-and-w-feather) |

## 本地重建与验证

在 `G:\samplePj\feather\specimen-study` 使用 Blender 5.2.4，按需执行对应阶段。命令使用现有 `G:\blender\app`，重建脚本复用上一级的 `build_wing.py`。`optics` 同时保存场景和内嵌图集，打开成品场景可直接检查材质与几何。GPU 渲染用 Cycles OptiX，构建命令末尾可添加 `--cpu`。

```powershell
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_study.py -- --stage shape
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_study.py -- --stage photo
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_study.py -- --stage optics
& 'G:\blender\app\blender.exe' -b --factory-startup --python-exit-code 7 -P build_study.py -- --stage coupon
& 'G:\blender\app\blender.exe' -b --factory-startup warbler-resting-study.blend --python-exit-code 7 -P verify_study.py
```

使用 Blender 5.2.4 和 RTX 4060 Laptop GPU 完成四阶段渲染。重开场景确认 197 枚独立羽片、3,750 条肩部绒羽曲线及两张内嵌 1408 × 1248 图集，解码 14 张阶段渲染并核对尺寸。单羽的侧光和背光对照确认材质更改引起像素变化，拟真度按画面目视判断。 [验证日志](verification.log)
