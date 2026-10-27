Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir

PythonwPath = ScriptDir & "\.venv\Scripts\pythonw.exe"
If FSO.FileExists(PythonwPath) Then
    WshShell.Run """" & PythonwPath & """ main.py", 0, False
Else
    WshShell.Run "pythonw.exe main.py", 0, False
End If
