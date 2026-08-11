' Launch Transfer Monitor with no visible PowerShell console (0 = hidden).
' Double-click this, or call from .bat / toolbox server.

Option Explicit
Dim sh, fso, here, ps1, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = here & "\TransferMonitor.ps1"

If Not fso.FileExists(ps1) Then
  MsgBox "Missing TransferMonitor.ps1 next to this launcher.", vbExclamation, "Transfer Monitor"
  WScript.Quit 1
End If

' 0 = hide window entirely (no console flash)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
sh.Run cmd, 0, False
WScript.Quit 0
