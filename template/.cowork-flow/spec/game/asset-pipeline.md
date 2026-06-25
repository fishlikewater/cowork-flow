# 资产管线约定

## 目录组织

推荐资产目录结构（引擎无关）：

```
Assets/
├── _Art/                    # 原始艺术资产（源文件）
│   ├── Models/              # 3D 模型源文件（.fbx, .blend, .ma）
│   ├── Textures/            # 贴图源文件（.psd, .tif, .exr）
│   ├── Materials/           # 材质源文件
│   └── Audio/               # 音频源文件（.wav, .flac）
├── _Game/                   # 运行时游戏资产
│   ├── Prefabs/             # 预制体
│   ├── Scenes/              # 场景文件
│   ├── ScriptableObjects/   # 数据配置
│   └── UI/                  # UI 资源
├── _Build/                  # 构建输出（只读）
│   ├── Bundles/             # AssetBundle / Pak 文件
│   └── Shaders/             # 编译后的着色器
└── ThirdParty/              # 第三方资产（只读）
    └── <vendor>/            # 按供应商分区
```

- 运行时路径用常量或配置中心管理，不硬编码字符串
- 同资产只有一份源拷贝，引用在预制体/资源列表中完成

## 构建管线阶段

```
原始资产 → 导入 → 烘焙/压缩 → 打包 → 部署
```

1. **导入** — 设置导入参数（压缩格式、纹理大小限制、网格 LOD）
2. **烘焙** — 光照贴图、NavMesh、遮挡剔除数据；可作为 CI 步骤
3. **压缩** — 纹理 ASTC/ETC2/BCx，音频 Vorbis/ADPCM，网格 Quantization
4. **打包** — 按场景/功能打包 AssetBundle，避免冗余
5. **部署** — 上传 CDN、增量更新、热更

## LOD 策略

- 每模型至少 2 级 LOD（LOD0 = 原始，LOD1 = ~50% 面数）
- LOD 切换距离由屏幕尺寸占比决定，非世界距离
- 最优 LOD Group Cross Fade 设置 = 0.5s 淡入淡出
- 极小物件（屏幕占比 <5%）用 Impostor（公告板）

## 版本控制

- 二进制资产（模型、贴图、音频）使用 Git LFS 跟踪
- LFS 模式设置为 `lockable` 防止合并冲突
- 场景文件和预制体建议用文本序列化格式（Unity `.scene.yaml`、Unreal `.uasset` text）
- `.gitignore` 排除编辑器生成产物（`.meta` 应保留、Library/Build 应排除）
