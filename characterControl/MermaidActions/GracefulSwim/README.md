# 人鱼泳姿 · 优雅与灵活

原始目标是让同一人鱼完成灵活游泳、转圈前进、摆尾悬停。上一版完成配色并采用人类划水动作。根据本轮反馈，降低上半身的重复动作，参考人鱼表演重新安排手臂和躯干的节奏。

| 时间 | 动作 |
| --- | --- |
| 0:00–0:05.6 | 下潜时一侧手臂轻扫引路，摆尾滑行。抬升时另一侧沿弧线展开，随后松弛回收。 |
| 0:05.6–0:11.6 | 向前翻转一圈。一手伸出领转，另一手收近身侧，出转时展开恢复平衡。 |
| 0:11.6–0:17.0 | 尾巴持续摆动，上身保持接近直立。手在较低的位置缓慢托水，两侧略错开。 |

- Hannah Fraser 在《Emanation》的公开画面提供了收臂和摆尾滑行的参考。《Mantas Last Dance》的公开画面提供了放松肩部、前臂微开的参考。[《Emanation》](https://www.youtube.com/watch?v=o0Epc6v9Z5A) · [《Mantas Last Dance》](https://www.youtube.com/watch?v=OzeOpudzJa4)
- Weeki Wachee 水下表演档案中的直立体态和低位开臂用于悬停姿势。[佛罗里达州档案](https://www.floridamemory.com/items/show/253622)

手腕目标沿弧线过渡，肘部按原骨架的上下臂长度求解。头和胸随下潜、抬升、翻转做小幅调整。手指保留轻微且错开的弯曲。保留上一版的模型、颜色、整体路线和尾鳍运动，三段沿用原来的镜头切点。

## 本地复检

逐帧检查了 510 帧，角色完整入镜，最小画面边距约 3.2%，与海床最近约 0.75 个场景单位。78 个取样帧中，手和前臂未与躯干、上衣、鱼尾或长发网格相交。收紧或展开手臂的关键帧也用渲染画面做了对照，第二轮把领转的折肘改成较舒展的弧形。

排除整体路线后，手腕相对肩部的平均速度在前游、转圈和悬停分别由 1.422 降至 0.184、由 0.257 降至 0.173、由 0.438 降至 0.058，单位为场景单位每秒。五节尾骨的位置逐帧与上版一致。

## 工程与重建

`Mermaid_GracefulSwim.blend` 包含骨骼关键帧与打包贴图，`Mermaid_GracefulSwim.mp4` 为 17 秒、30 fps 的本地预览。保留 `ColoredSwim` 作为生成起点。方案沿用现成 Blender 工程和骨架，参考全局 `G:\selftool\resourceforlater\docs\FRAMEWORK_PREFERENCES.md` 的本地、简单实现偏好。项目目录与说明中未找到独立的人鱼设计备忘录。

从本目录执行以下命令可生成新版工程并渲染 PNG 序列。

```powershell
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec ..\ColoredSwim\Mermaid_ColoredSwim.blend --python-exit-code 9 --python .\mermaid_glide.py -- .\rebuilt
& 'G:\blender\app\blender.exe' --background --factory-startup --disable-autoexec --gpu-backend vulkan .\rebuilt\Mermaid_GracefulSwim.blend --python-exit-code 9 --python ..\render_mermaid.py -- .\frames
```
