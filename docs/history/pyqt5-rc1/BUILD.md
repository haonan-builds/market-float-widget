# Build v0.1.0-rc.1 on Windows x64

Use Windows x64 and CPython 3.12.0 to match the candidate. Run from the extracted source directory in PowerShell.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm crypto_float.spec
Get-FileHash -Algorithm SHA256 .\dist\crypto_float.exe
(Get-Item .\dist\crypto_float.exe).VersionInfo | Select-Object ProductVersion, FileVersion
```

Expected metadata: ProductVersion `0.1.0-rc.1`, FileVersion `0.1.0.1`. The GUI still shows the application version `0.1.0`. The build is not claimed to be bit-for-bit reproducible.

The candidate was built in the existing offline acceptance venv with the pinned requirements. Online installation using these commands on a fresh machine is a separate check. For public release, preserve the exact wheel hashes and matching dependency sources with the build inputs. See [Distribution](DISTRIBUTION.md).
