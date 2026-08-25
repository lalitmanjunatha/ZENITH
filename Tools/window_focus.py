import pygetwindow as gw
import asyncio
from livekit.agents import function_tool


@function_tool()
async def focus_window(window_title: str) -> str:
    """
    Focuses on a specific window by title.
    
    Args:
        window_title: Title or partial title of the window to focus
    
    Returns:
        str: Focus confirmation or error message
    """
    try:
        # Find window by title matching
        all_windows = await asyncio.to_thread(gw.getAllWindows)
        target_window = None
        
        for win in all_windows:
            if win and win.title:
                win_title = win.title.strip()
                if window_title.lower() in win_title.lower():
                    target_window = win
                    break
        
        if not target_window:
            return f"❌ '{window_title}' title ki koi window nahi mili. Available windows dikhane ke liye 'list windows' command use karein."
        
        # Try to activate the window
        try:
            await asyncio.to_thread(target_window.activate)
            await asyncio.sleep(0.5)
            return f"✅ Window focus kiya gaya: '{target_window.title}'"
        except Exception as e:
            return f"⚠️ Window activate karne mein error: {str(e)}. Lekin window dhundi gayi hai."
        
    except Exception as e:
        return f"🚫 Error finding window: {str(e)}"


@function_tool()
async def list_windows_with_details() -> str:
    """
    Lists all visible windows with their details (size, position, state).
    
    Returns:
        str: Formatted list of all windows
    """
    try:
        all_windows = await asyncio.to_thread(gw.getAllWindows)
        result = []
        
        for window in all_windows:
            if window and window.title:
                try:
                    is_minimized = await asyncio.to_thread(lambda: window.isMinimized)
                    is_maximized = await asyncio.to_thread(lambda: window.isMaximized)
                    is_active = await asyncio.to_thread(lambda: window.isActive)
                    width, height = await asyncio.to_thread(window.size)
                    left, top = await asyncio.to_thread(window.tl_cords)
                    
                    status = "Minimized" if is_minimized else "Maximized" if is_maximized else "Active"
                    if is_active:
                        status = "Active"
                    
                    result.append(f"• {window.title.strip()}")
                    result.append(f"   Size: {width}x{height}, Position: ({left}, {top}), Status: {status}")
                except Exception:
                    result.append(f"• {window.title.strip()} (details not available)")
        
        if result:
            return f"🪟 All visible windows:\n" + "\n".join(result)
        else:
            return "❌ koi visible window nahi mili"
        
    except Exception as e:
        return f"🚫 Error listing windows: {str(e)}"


@function_tool()
async def minimize_all_windows() -> str:
    """
    Minimizes all open windows to show desktop.
    
    Returns:
        str: Confirmation message
    """
    try:
        await asyncio.to_thread(pyautogui.hotkey, 'win', 'd')
        return "🖥️ Sari windows minimize karke desktop dikhaya gaya."
    except Exception as e:
        return f"🚫 Error minimizing windows: {str(e)}"


@function_tool()
async def restore_all_windows() -> str:
    """
    Restores all minimized windows.
    
    Returns:
        str: Confirmation message
    """
    try:
        # Win+D again restores minimized windows
        await asyncio.to_thread(pyautogui.hotkey, 'win', 'd')
        return "🖥️ Sari minimized windows restore kar di gayi."
    except Exception as e:
        return f"🚫 Error restoring windows: {str(e)}"