# blastView 本地试用

这是 [tegos/cad-3d-viewer](https://github.com/tegos/cad-3d-viewer/tree/83756548e6f450de84ec67ce475dae78f53075cc) 的本地副本。默认展示小型 PCB 装配，示例菜单里还有完整的 SO-101 机械臂。授权说明见 `LICENSE`、`LICENSE-APACHE-2.0` 和 `public/samples/ATTRIBUTION.md`。

在本目录打开 PowerShell，运行：

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

打开 [本地演示](http://127.0.0.1:8765/)。模型加载后，将左侧 **Explode** 滑杆从 0% 拖向 100%。拖动模型可旋转，滚轮可缩放。可在 **Or load a sample** 切换到 SO-101，首次解析较慢。也可以拖入自己的多零件 STEP 装配。

`dist` 已编译，模型、解析器和光照素材均在本地。运行演示只需要 Python 和支持 WebGL2 的浏览器。要修改源码并重建，运行 `npm ci` 和 `npm run build`。

本地副本还修正了被无几何外层节点包裹的 STEP 装配无法启用爆炸滑杆的问题。
