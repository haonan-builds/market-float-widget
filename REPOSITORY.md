# GitHub repository layout

```text
market-float-widget/
  crypto_float.py
  crypto_float.spec
  version-info.txt
  requirements.txt
  requirements-build.txt
  README.md / README_CN.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  DISTRIBUTION.md
  BUILD.md
  RELEASE_CHECKLIST.md
  RELEASE_NOTES.md
  CORRESPONDING_SOURCE.md
  BUNDLED_FILES.tsv
  CHANGELOG.md
  .gitignore
  docs/screenshots/
  licenses/
  tests/
```

将源码 ZIP 解压后的项目内容提交到仓库根目录。仓库公开后复查 README 的链接和截图。构建目录、虚拟环境、配置和 EXE 保持在仓库之外。完成发布清单后再将候选版标记为 GitHub pre-release，并在同一发布页提供 EXE、哈希、完整第三方声明和对应源码入口。最终版使用独立的 `v0.1.0` 标签及该构建自己的哈希。

首次 GitHub 公开以源码仓库为范围。EXE 的公开分发另按 [发布检查清单](RELEASE_CHECKLIST.md) 验收。
