# 对应源码材料

RC1 已对照 PyQt5、PyQt5-Qt5、PyQt5-sip、websocket-client、PyInstaller 五个官方 wheel 的下载 SHA-256 及已比对的安装 payload。此证据核实二进制输入的来源范围。以下源码归档的下载校验与构建对应核对是不同步骤。

| 组件 | 上游归档 | 下载校验 | 上游 SHA-256 |
|---|---|---|---|
| PyQt5 5.15.11 | [PyQt5-5.15.11.tar.gz](https://files.pythonhosted.org/packages/0e/07/c9ed0bd428df6f87183fca565a79fee19fa7c88c7f00a7f011ab4379e77a/PyQt5-5.15.11.tar.gz) | 归档 SHA-256 匹配 | `fda45743ebb4a27b4b1a51c6d8ef455c4c1b5d610c90d2934c7802b5c1557c52` |
| PyQt5-sip 12.20.0 | [pyqt5_sip-12.20.0.tar.gz](https://files.pythonhosted.org/packages/cd/ab/835df8e6fb06a618a4b8664765c5598e933c8113e90448e294549c9447f7/pyqt5_sip-12.20.0.tar.gz) | 归档 SHA-256 匹配 | `93e0622791f8d22cd4a32a29edfdd2ef6d6680f4c47f59b03ebf1c5da3c3e896` |
| websocket-client 1.9.2 | [websocket_client-1.9.2.tar.gz](https://files.pythonhosted.org/packages/d8/cb/a5abcc2891249f393827c650c6296660ce40374ac22d99ab9aea41f9d2a2/websocket_client-1.9.2.tar.gz) | 归档 SHA-256 匹配 | `0fcb57545848be86992e128218fd96dd87a6769ffdb1a968dff79632b85604d0` |
| PyInstaller 6.22.3 | [pyinstaller-6.22.3.tar.gz](https://files.pythonhosted.org/packages/63/41/f90302845945abd4ed647933ff5ee7c6ac93983187be67f897b6cb613331/pyinstaller-6.22.3.tar.gz) | 归档 SHA-256 匹配 | `05eb2f5615503e72939a7224d68b4aff572c6b0438ee4a17d0a4b481f399362d` |

**完整对应源码仍为 Not Verified。** 还需核对官方 wheel 的生成与构建脚本、补丁、编译参数、实际打包的 Qt 插件和内嵌第三方库、CPython 及运行库的对应材料，并记录是否存在本地修改。应用本身的源码、spec 和依赖版本随本源码包提供。见 [依赖审计](DEPENDENCY_AUDIT.md)。

完成二进制发布前，用每个实际依赖的确切源码和适用的构建、安装信息组成完整包，并在同一 Release 提供等同下载。适用例外须记录依据。原生清单和上游归档仅用于审计，完整交付要求见 [分发说明](DISTRIBUTION.md)。
