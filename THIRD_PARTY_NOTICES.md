# Third-party software notices

Original Market Float Widget code: MIT, copyright 2026 Haonan build.
This notice does not replace the licenses in the `licenses/` directory.

| Component | Version used for this build | License / role |
|---|---|---|
| Python | 3.12.0 | PSF license and bundled component notices; runtime |
| PyQt5 | 5.15.11 | GPL v3 (commercial license not verified); runtime bindings |
| Qt | 5.15.2 | LGPL v3 package; individual modules/components may carry additional terms |
| PyQt5-sip | 12.20.0 | BSD-2-Clause; runtime |
| websocket-client | 1.9.2 | Apache-2.0; runtime |
| PyInstaller | 6.22.3 | GPL-2.0-or-later with bootloader exception; runtime hooks Apache-2.0 |
| altgraph | 0.17.5 | MIT; build tool dependency |
| packaging | 26.3 | Apache-2.0 or BSD; build tool dependency |
| pefile | 2024.8.26 | MIT; build tool dependency |
| pyinstaller-hooks-contrib | 2026.9 | GPL-2.0-or-later with exceptions; build hooks |
| pywin32-ctypes | 0.2.3 | BSD-style; build dependency |
| setuptools | 84.2.1 | MIT and vendored licenses; build dependency |

The combined EXE uses GPL PyQt5; it is not an MIT-only binary. Original source remains MIT-compatible, while distribution of the combined application must satisfy applicable GPL terms. See DISTRIBUTION.md.

License texts were copied from the installed distributions used for this test build. The Qt distribution's LICENSE includes GPL v3 and LGPL v3 texts. Python's LICENSE includes bundled component notices. This inventory identifies principal dependencies; completion of Qt's module-specific third-party notices and corresponding-source distribution remains a public binary release blocker. A public download URL alone does not prove source availability is under the distributor's control.

本测试 EXE 包含 GPL 版 PyQt5，不是仅 MIT 授权的二进制文件。本项目自有源码仍保留 MIT；组合程序须满足 GPL 分发要求。已附主要许可证文本，但 Qt 模块相关的第三方声明及对应源码分发尚需完成，因此该构建不能直接作为正式公开发行版。

Official references:

- https://www.riverbankcomputing.com/software/pyqt
- https://www.qt.io/development/open-source-lgpl-obligations
- https://www.qt.io/faq/qt-open-source-licensing
- https://docs.python.org/3.12/license.html
- https://pyinstaller.org/en/stable/license.html
