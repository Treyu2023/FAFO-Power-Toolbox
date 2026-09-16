Option Explicit
Dim sh, fso, here, ps1, cmd, ps
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = here & "\PinokioDock.ps1"
If Not fso.FileExists(ps1) Then
  MsgBox "Missing PinokioDock.ps1 in " & here, vbExclamation, "Pinokio Dock"
  WScript.Quit 1
End If
ps = "powershell.exe"
cmd = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
' WindowStyle 0 = hidden; use Run with full command line as one string
sh.Run ps & " " & cmd, 0, False