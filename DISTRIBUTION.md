# v0.1.0-rc.1 分发方案 / Distribution plan

保留项目原有 MIT 授权与版权声明。建议公开分发时将 **Market Float Widget 与 GPL 版 PyQt5 组合后的应用整体按 GPL-3.0-only 提供**，同时保留各组件原有许可及声明。MIT 许可允许将项目代码纳入 GPLv3 组合程序。无需替换根目录 LICENSE，也无需撤销已有 MIT 授权。若希望项目自有源码以后只按 GPLv3 授权，须先确认所有相关权利人的授权，本 RC 不采用该方案。

Keep the MIT grant for original project files. Distribute the combined application with GPL PyQt5 under GPL-3.0-only, retaining the original terms and notices for individual components. The bundled license texts do not replace the Corresponding Source.

| 实际组件 | 条款与交付要求 |
|---|---|
| PyQt5 5.15.11 | 本构建采用 GPL v3 版本。提供对应绑定源码、补丁、生成与构建输入，并随组合程序提供 GPLv3 全文。 |
| Qt 5.15.2 和插件 | wheel 标注 LGPLv3。逐项核对所含模块及内嵌第三方代码。建议对允许此选项的 Qt 代码按 GPLv3 路径随整体分发，保留上游声明及原许可证。若选择沿用 LGPLv3 组合分发路径，另验证第 4 节所需的替换或重新链接能力，单文件自解包本身不足以证明。 |
| PyQt5-sip 12.20.0、websocket-client 1.9.2 | 分别保留 BSD-2-Clause 与 Apache-2.0 文本、版权及适用 NOTICE。将所用版本源文件纳入对应源码材料。 |
| CPython 3.12.0、Windows 运行库、OpenSSL 等 | 按实际归档逐项核对 Python 随附组件、OpenSSL 版本及授权、Windows DLL 的再分发资格。保留对应版权声明。系统库例外只能在核实适用条件后使用。 |
| PyInstaller 6.22.3 及运行钩子 | 保留 bootloader 例外和钩子适用许可。构建依赖与实际嵌入文件分开审计。例外不覆盖 PyQt 或 Qt。 |

公开下载采用 GPLv3 §6(d) 路径。在同一 Release 给二进制与对应源码提供同等下载入口，源码无需额外付费。源码包包括应用和组合程序对应依赖的确切源码、补丁、配置和控制编译与安装的脚本。为每个归档记录版本、上游来源、SHA-256 和与实际 DLL/wheel 的对应证据。仅列通用上游主页、版本号或 GitHub 自动生成的应用源码 ZIP 无法完成这一步。

1. 核实构建输入的来源和哈希。当前 RC 使用上一轮离线恢复的本地依赖，RECORD 校验能发现本地文件不一致，不能证明官方 wheel 身份或 Qt wheel 的准确构建来源。
2. 从 Riverbank/PyPI、Qt、CPython 和其他组件上游取得匹配版本的源码与构建材料。对 Qt 逐个核对实际模块、插件、静态带入的第三方组件、补丁和构建参数。若现有 wheel 无法建立对应关系，用可追溯的依赖重建 RC，再重复实机验收。
3. 把核验后的对应源码和完整第三方声明作为 Release 附件交付。发布页明确标注组合程序 GPL-3.0-only，并在 EXE 下载附近标出对应源码。验收匿名下载和哈希。

当前 RC 仅供本地验收。对应源码与完整运行库、Qt 模块声明仍是公开 EXE 的阻塞项。源码 ZIP 仅包含项目源码和文档，可用作仓库提交内容。

参考 / References

- [GNU GPL v3 §5–6](https://www.gnu.org/licenses/gpl-3.0.html)
- [GNU LGPL v3 §2–4](https://www.gnu.org/licenses/lgpl-3.0.html)
- [GNU license compatibility FAQ](https://www.gnu.org/licenses/gpl-faq.en.html)
- [Riverbank PyQt licensing](https://www.riverbankcomputing.com/software/pyqt)
- [Qt open-source obligations](https://www.qt.io/development/open-source-lgpl-obligations)
- [PyInstaller license](https://pyinstaller.org/en/stable/license.html)


## 首次 GitHub 源码公开 / Initial source publication

应用源码、构建脚本和许可文档可分阶段公开。项目权利和署名已由 Haonan build 确认。首次公开的仓库及发布附件以源码为范围，二进制另行验收。第三方许可证文本与清单用于说明后续构建涉及的组件。保留原始 MIT 许可与声明。

The initial public repository contains project source, build scripts and licensing documents. Haonan build has confirmed publication rights and attribution. Binary publication has a separate gate. See [Copyright review](COPYRIGHT_REVIEW.md), [Dependency audit](DEPENDENCY_AUDIT.md) and [release checklist](RELEASE_CHECKLIST.md).

## 条款核对

MIT 授予复制、修改和分发权限，同时要求保留版权与许可声明。它与 GPLv3 兼容。对采用 GPL 版 PyQt5 的组合程序，本项目选择 GPLv3 整体分发路径，GPLv3 §5 和 §6 分别规定组合源码与目标代码分发条件。选择 GPL-3.0-only 是此项目的拟定分发方式，适用前提是实际组件均允许该组合，并满足它们的独立条款。

Qt 若选择按 LGPLv3 组合应用路径分发，需单独验证 LGPLv3 §4 的声明和替换或重新链接条件。若使用 LGPLv3 §2 所允许的 GPL 路径，仍须逐文件核对适用条款及其例外。有关完整对应源码、安装信息和系统库例外的判断须按实际二进制、交付形式和 GPLv3 §§1、6 条件核实。普通 Windows 下载是否触发 User Product 安装信息义务取决于实际交付，当前为 Not Verified。
