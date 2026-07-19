1. Restore the Classic Right-Click Menu
Windows 11 hides third-party editing tools (like Notepad++, ExifTool, or Python scripts) behind the "Show more options" button. This registry edit disables the new Windows 11 context menu and permanently restores the classic Windows 10 menu, giving you instant one-click access to all your tools.

2. Enable Win32 Long Paths (Crucial for AI/Docker)
Windows natively restricts file paths to 260 characters. Local AI workloads (like ComfyUI, Pinokio) and Docker containers frequently generate deeply nested folder structures and custom node directories that exceed this limit. Hitting the 260-character ceiling will cause Python scripts and installations to silently fail. This script removes that limit.

3. Disable Bing Search in the Start Menu
A high-end system with an i9-14900K and an RTX 4090 should never stutter when you hit the Windows key to search for a local app or file. However, Windows 11 forces a web query to Bing every time you type, causing unnecessary lag. This script disables web search in the Start Menu, restricting it strictly to local files, settings, and apps for instant results.


1. Speed Up Explorer (Disable Folder Sniffing)When you open a folder packed with media, Windows pauses to scan the files, generate thumbnails, and decide if it should apply a "Video," "Picture," or "Document" layout. This "content sniffing" causes heavy folders to hang. This script forces Windows to treat every folder as a generic list instantly, bypassing the scan.  (Bonus: This also permanently stops the Downloads folder from stubbornly grouping your files by "Date Modified".)

2. Add "Copy To" and "Move To" in the Right-Click Menu
Dragging and dropping files across multiple NVMe drives or external HDDs can lead to accidental drops in the wrong folder. This classic registry tweak adds dedicated Copy To folder... and Move To folder... options directly to your right-click menu. Clicking them opens a precise directory tree popup so you can route files exactly where they belong.

3. Force Show File Extensions and Hidden Files
Windows hides file extensions by default to look cleaner. When you are managing various formats or troubleshooting code, knowing whether a file is .mp4, .mkv, .png, or .webp at a glance is critical. This script forces extensions to always show, and unhides hidden system/app data folders (like .git or .docker caches).