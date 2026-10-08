# Iconify 离线资源

本目录的 `manifest.json` 与 `iconify-json-2.2.458.tar.gz` 来自 `frontend/pnpm-lock.yaml` 已锁定的官方 `@iconify/json@2.2.458` 包。归档较大，不纳入 Git；交付内网时需连同此目录复制。`collections.json`、所有集合 JSON、作者与许可证元数据、包元信息都在归档内。该发布包有 230 个集合 JSON，其中 5 个没有 `collections.json` 索引条目；清单列出了这 5 个前缀，不将它们误报为缺失。

在项目根目录运行：

```powershell
python frontend/scripts/prepare_iconify_snapshot.py --verify
```

需要重新制包时，省略 `--verify`。脚本核对集合索引、分别统计图标与别名，并写入每个文件及归档的 SHA-256。归档校验逐项读取归档内容，不依赖现有 `node_modules`。

前端页面只使用 `frontend/src/assets/iconify/feature-center-icons.ts` 的小型图标子集。源码选型与验证：

```powershell
cd frontend
pnpm icons:search mdi layers
pnpm icons:generate
pnpm icons:check
```

复材对象固定映射：叠层 `mdi:layers-triple-outline`、铺层组 `mdi:folder-multiple-outline`、序列 `mdi:format-list-numbered`、单层 `mdi:rhombus-outline`。原型应标明现有 Iconify ID；新增图标先从本地锁定图库查找，再生成并提交子集。业务图标使用主题色及语义状态色，尺寸以窄面板为准。生成脚本使用 `@iconify/utils.getIconData` 展开别名及变换，不让浏览器加载全量图库。Feature Center 中未知图标使用已打包的中性占位，不向公网请求。

内网运行已构建页面只需部署前端产物和项目 API。内网从源码重建还需要与锁文件匹配的 pnpm 全依赖缓存、Node 与 pnpm；本归档自身不能替代依赖缓存。先在联网机器执行 `pnpm fetch --prod=false --frozen-lockfile`，将 pnpm store 一并搬运。当前 Windows 隔离目录已验证 `pnpm install --offline --ignore-scripts --frozen-lockfile`、`pnpm icons:check` 和 `pnpm build`；去掉 `--ignore-scripts` 后的离线安装仍需逐平台验证原生依赖安装脚本。Windows 依赖缓存或 `node_modules` 不代表 Linux 安装已验证。
