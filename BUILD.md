# Development checks

Use the README Python 3.12 venv, then run from repository root:

    .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
    .\.venv\Scripts\python.exe -m pip check
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

No current binary release spec is supplied. The historical PyQt5 spec and version metadata are archived. Internal packaging does not establish public distribution compliance.
