# 性能约定

## 帧率目标

| 平台 | 目标 FPS | 最低 FPS | 说明 |
|------|---------|---------|------|
| PC 高端 | 120+ | 60 | 竞技类优先帧率一致性 |
| PC 主流 | 60 | 30 | 开放世界/AAA |
| 移动端 | 30 | 20 | 复杂场景下允许动态降质 |
| VR | 72/90 | 72 | 低于目标会导致晕动症 |

- 每帧渲染耗时预算 = 1000ms / 目标 FPS × 0.9（预留 10% 余量）
- 逻辑帧与渲染帧解耦（固定时间步长，可变渲染帧率）

## 内存预算

| 平台 | 总内存 | 游戏内容上限 | 系统/OS 预留 |
|------|-------|------------|------------|
| PC (8GB) | 8 GB | 5 GB | 3 GB |
| PC (16GB) | 16 GB | 10 GB | 6 GB |
| iOS 高端 | 6 GB | 3 GB | 3 GB |
| iOS 主流 | 4 GB | 1.8 GB | 2.2 GB |
| Android 6GB | 6 GB | 2.5 GB | 3.5 GB |
| Android 4GB | 4 GB | 1.5 GB | 2.5 GB |

- 纹理压缩：移动端用 ASTC（Android）/ PVRTC（iOS），桌面用 BC7
- 音频内存：常驻音效 < 50MB，流式加载背景音乐
- 每帧分配 < 1KB 的临时内存（避免 GC 压力）

## GC 管理

- 每帧 GC 分配预算：< 2KB（移动端），< 8KB（PC）
- 高频调用的路径（每帧 Update）禁止 `new` 分配
- 使用对象池（`ObjectPool<T>`）复用高频对象：子弹、粒子、伤害数字
- 结构体（struct）在栈上分配，不触发 GC，适合临时数据
- 字符串拼接用 `StringBuilder` 或字符串常量，避免 `+` 运算符
- 协程、Lambda 捕获、LINQ 查询需要额外 GC 分配，在性能路径上避免使用

## 渲染

- Draw Call 预算：移动端 < 100，PC < 2000
- 静态/动态批处理：优先 SRP Batcher（URP/HDRP），Static Batching 次之
- 合批策略：相同材质 → GPU Instancing，不同材质 → Atlas/Texture Array
- 剔除：视锥剔除 + Occlusion Culling + 距离剔除（Layer-based）
- 后处理开销：移动端禁用 HDR 和全屏 Bloom，PC 按质量等级控制

## 性能分析工作流

```
profiling → hotspot identification → optimization → regression verification
```

1. **Profiling** — 用 Profiler（Unity Profiler / Unreal Insights）收集帧数据
2. **Hotspot identification** — 定位 CPU/GPU 瓶颈：Profiler Timeline → Hierarchy 排序
3. **Optimization** — 针对热点做最简改动（减少分配、合并 draw call、下调纹理尺寸）
4. **Regression verification** — 重新 Profiling 确认改进 + 确认未引入新性能问题

性能测试在 CI 中保留基线：`tests/performance/` 记录关键场景的帧时间、内存、Draw Call 快照。
