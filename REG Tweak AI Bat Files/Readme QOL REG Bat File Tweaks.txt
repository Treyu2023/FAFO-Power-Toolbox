Windows REG QoL Tweaks
======================

The HTML desk (Windows REG QoL Tweaks.html) scans whether each fix is already
applied, colors the card (green = on, amber = not yet), and sorts applied ones
to the top. Re-apply is always allowed. Both first-time and repeat writes ask
for confirmation.

Core
----
1. Restore the Classic Right-Click Menu
Windows 11 hides third-party editing tools (like Notepad++, ExifTool, or Python scripts) behind the "Show more options" button. This registry edit disables the new Windows 11 context menu and permanently restores the classic Windows 10 menu, giving you instant one-click access to all your tools.

2. Enable Win32 Long Paths (Crucial for AI/Docker)
Windows natively restricts file paths to 260 characters. Local AI workloads (like ComfyUI, Pinokio) and Docker containers frequently generate deeply nested folder structures and custom node directories that exceed this limit. Hitting the 260-character ceiling will cause Python scripts and installations to silently fail. This script removes that limit.

3. Speed Up Explorer (Disable Folder Sniffing)
When you open a folder packed with media, Windows pauses to scan the files, generate thumbnails, and decide if it should apply a "Video," "Picture," or "Document" layout. This "content sniffing" causes heavy folders to hang. This script forces Windows to treat every folder as a generic list instantly, bypassing the scan.  (Bonus: This also permanently stops the Downloads folder from stubbornly grouping your files by "Date Modified".)

4. Add "Copy To" and "Move To" in the Right-Click Menu
Dragging and dropping files across multiple NVMe drives or external HDDs can lead to accidental drops in the wrong folder. This classic registry tweak adds dedicated Copy To folder... and Move To folder... options directly to your right-click menu. Clicking them opens a precise directory tree popup so you can route files exactly where they belong.

5. Force Show File Extensions and Hidden Files
Windows hides file extensions by default to look cleaner. When you are managing various formats or troubleshooting code, knowing whether a file is .mp4, .mkv, .png, or .webp at a glance is critical. This script forces extensions to always show, and unhides hidden system/app data folders (like .git or .docker caches).

6. Regedit Fix Notepad
Rebuilds .txt as a real text file and restores New > Text Document when Store Notepad or a broken association gets in the way.

Optional
--------
7. Disable Bing Web Search in Start
A high-end system should never stutter when you hit the Windows key to search for a local app or file. Windows 11 forces a web query to Bing every time you type. This restricts Start search to local files, settings, and apps.

8. Show Seconds on the Clock
Puts seconds on the notification-area clock — useful when timing encodes, captures, or waiting on a reboot.

9. Hide Widgets / News Button
Removes the Widgets / News and Interests button so weather and MSN feed clicks stop stealing focus.

10. End Task from the Taskbar
Adds End task to a right-click on a running app's taskbar icon (Windows 11 22H2+). Faster than opening Task Manager for a stuck preview.

11. Explorer Opens to This PC
File Explorer starts on This PC instead of Home / Quick Access.

12. Disable Aero Shake Minimize
Stops grabbing a window title bar and shaking it from minimizing everything else — a common accident on a crowded compare desktop.

13. Instant Menus (No Hover Delay)
Sets MenuShowDelay to 0 so cascading right-click menus open immediately.

14. Disable Start & Lock Suggestions
Turns off lock-screen fun facts, Start suggestions, and silent Store app installs.

15. Disable Sticky Keys Popup
Stops the Sticky Keys / Filter Keys prompt when Shift is held during long keyboard work.

16. Verbose Startup / Shutdown Status
Shows the real driver / service names during boot and shutdown instead of generic Please wait. Needs Administrator.
