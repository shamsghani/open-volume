Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
If CreateObject("Scripting.FileSystemObject").FileExists("target\release\open-volume.exe") Then
    WshShell.Run "target\release\open-volume.exe", 0, False
Else
    WshShell.Run "pythonw.exe main.py", 0, False
End If
Set WshShell = Nothing

