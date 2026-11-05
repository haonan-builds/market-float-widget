# Windows RC1 依赖与许可审计

审计对象是已构建的 v0.1.0-rc.1 EXE。它嵌入的是构建当时的文档。[BUNDLED_FILES.tsv](BUNDLED_FILES.tsv) 记录外层归档，[RC_NATIVE_INVENTORY.tsv](RC_NATIVE_INVENTORY.tsv) 记录 DLL/PYD 的文件版本、哈希及与官方 Qt wheel 逐字节比对结果。PE 文件版本不能证明编译参数、补丁或上游源码对应关系。

## Qt

来源为 Riverbank 发布的 PyQt5-Qt5 5.15.2 Windows amd64 wheel，SHA-256 为 `750b78e4dba6bdf1607febedc08738e318ea09e9b10aea9ff0d73073f11f6962`。归档内 Qt 路径下有 35 个原生文件，其中 31 个与官方 wheel 的同路径文件逐字节一致。其余 4 个为 wheel 同路径未提供的 MSVCP/VCRUNTIME DLL，路径归属不足以证明来源。

Qt 模块：Qt5Core 5.15.2.0, Qt5DBus 5.15.2.0, Qt5Gui 5.15.2.0, Qt5Network 5.15.2.0, Qt5Qml 5.15.2.0, Qt5QmlModels 5.15.2.0, Qt5Quick 5.15.2.0, Qt5Svg 5.15.2.0, Qt5WebSockets 5.15.2.0, Qt5Widgets 5.15.2.0。实际插件覆盖 generic、iconengines、imageformats、platforms、platformthemes 与 styles，包含 qwindows 等。完整文件名见清单。图形 DLL 还含 libEGL、libGLESv2、opengl32sw 和 D3DCompiler。Qt 标注 LGPLv3 的 wheel 许可可核对，单个插件及内嵌第三方许可、Qt 工具链和构建参数、补丁集及源码对应关系均为 **Not Verified**。

向 Riverbank 核对该 wheel 的 Qt 源码快照、构建配置、补丁及第三方组件声明。用 [Qt 5.15.2 官方源码](https://download.qt.io/archive/qt/5.15/5.15.2/single/) 作为核对基线，对照对应模块源树和第三方元数据，包含实际构建启用的图像解码、字体、图形等内嵌库。无法证明现有 DLL 的对应关系时，公开 EXE 需使用来源可追溯的等版本构建输入，随后重新验收。当前任务保持既有依赖版本。

| 组件 | 授权及核对结果 | 公开 EXE 待办 |
|---|---|---|
| PyQt5 5.15.11 | GPLv3 wheel，Riverbank，QtCore/QtGui/QtWidgets 扩展 | 对应绑定源码归档已校验。核实 wheel 构建配置、SIP 生成输入、补丁及适用声明。 |
| PyQt5-sip 12.20.0 | BSD-2-Clause，CPython 3.12 扩展 | 保留版权和许可证，校验构建输入及修改记录。 |
| websocket-client 1.9.2 | Apache-2.0，打包 Python 模块 | 保留许可证及适用 NOTICE，提供实际所用源码与变更记录。 |
| Qt 5.15.2 | LGPLv3 wheel，逐模块条款 Not Verified | 按上述路径建立精确源码对应关系及第三方声明。 |
| PyInstaller 6.22.3 | 适用文件为 GPL-2.0-or-later 与 Bootloader Exception，部分 runtime hooks 为 Apache-2.0 | 例外允许将适用的未修改 bootloader 随应用分发，不能免除应用依赖义务。确认嵌入文件的例外及 Apache 声明，独立分发或修改 PyInstaller 时另审。 |
| CPython 3.12.0 与扩展 | PSF 及随附组件条款，含标准库与 DLL | 对照官方 Windows 安装件及 PCbuild 输入。逐项核对 OpenSSL、libffi、bzip2、XZ、Expat 等实际使用组件的版本、版权和适用文本。 |
| OpenSSL 3、libffi | libssl 与 libcrypto 的 PE 版本均为 3.0.11.0。OpenSSL 3 系列采用 Apache-2.0。libffi-8.dll 没有可用的 PE 版本，具体版本 Not Verified。 | 对照 CPython 的 Windows 构建输入和实际 DLL，核实许可证及 NOTICE，并取得匹配源码和构建说明。完整出处 Not Verified。 |
| MSVC、UCRT/API-set、D3DCompiler | 原生清单确认随包。具体再分发权 Not Verified | 对照来源、版本、适用 Microsoft 条款及 REDIST 清单，单独确认再分发资格和系统库例外适用性。 |
| 构建依赖 | altgraph、packaging、pefile、hooks-contrib、pywin32-ctypes、setuptools 的许可文本已保留 | 不能由安装清单推断已打包。区分构建工具与实际归档中的钩子和模块，核对相应文件条款。 |

现有上游材料、验证范围与未闭合项见 [CORRESPONDING_SOURCE.md](CORRESPONDING_SOURCE.md)。上游 LICENSE 与既有主许可文本可用，完整逐组件归因和对应源码仍有缺口。

参考：[Riverbank](https://www.riverbankcomputing.com/software/pyqt) · [Qt wheel](https://pypi.org/project/PyQt5-Qt5/5.15.2/) · [Qt 义务](https://www.qt.io/development/open-source-lgpl-obligations) · [PyInstaller](https://pyinstaller.org/en/stable/license.html) · [CPython](https://docs.python.org/3.12/license.html) · [OpenSSL](https://openssl-library.org/source/license/) · [Microsoft REDIST](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files)
