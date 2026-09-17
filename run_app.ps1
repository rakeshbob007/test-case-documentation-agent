# Always launches with the real (non-sandboxed) Python install, so the app can
# see files outside a few whitelisted folders (e.g. the claude CLI shim,
# your chosen output folder). The 'python'/'streamlit' commands on PATH can
# resolve to the sandboxed Microsoft Store Python instead, which silently
# fails to find files like C:\Users\<you>\AppData\Roaming\npm\claude.cmd.
$py = "C:\Users\rakesh.kodigandla\AppData\Local\Python\bin\python.exe"
& $py -m streamlit run "$PSScriptRoot\app.py"
