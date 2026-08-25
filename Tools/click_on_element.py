import pyautogui
import asyncio
import time
from difflib import SequenceMatcher
from livekit.agents import function_tool


def similarity(text1: str, text2: str) -> float:
    return SequenceMatcher(None, text1.lower().strip(), text2.lower().strip()).ratio()


@function_tool()
async def click_on_element(target_text: str, tolerance: float = 0.7) -> str:
    """
    Clicks on screen element found by OCR text matching.
    
    Args:
        target_text: Text of the element to click
        tolerance: Similarity threshold (0-1, default 0.7)
    
    Returns:
        str: Click confirmation or error message
    """
    try:
        # Take screenshot
        screenshot = await asyncio.to_thread(pyautogui.screenshot)
        screenshot_np = __import__('cv2').cvtColor(
            __import__('numpy').array(screenshot), 
            __import__('cv2').COLOR_RGB2BGR
        )
        
        # Run OCR
        import pytesseract
        data = await asyncio.to_thread(
            pytesseract.image_to_data,
            screenshot_np,
            output_type=pytesseract.Output.DICT
        )
        
        # Find best match
        best_match = None
        best_score = 0
        
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if not text:
                continue
            
            score = similarity(target_text, text)
            if score > best_score and score >= tolerance:
                best_score = score
                best_match = {
                    'text': text,
                    'x': int(data['left'][i]),
                    'y': int(data['top'][i]),
                    'w': int(data['width'][i]),
                    'h': int(data['height'][i]),
                }
        
        if not best_match:
            return f"❌ '{target_text}' पर screen par nahi mila. Visible texts dikhakar try karein."
        
        # Calculate center position
        center_x = best_match['x'] + best_match['w'] // 2
        center_y = best_match['y'] + best_match['h'] // 2
        
        # Get original mouse position
        original_pos = await asyncio.to_thread(pyautogui.position)
        
        # Move to and click
        await asyncio.to_thread(pyautogui.moveTo, center_x, center_y, duration=0.3)
        await asyncio.to_thread(pyautogui.click)
        
        # Restore mouse position
        await asyncio.to_thread(pyautogui.moveTo, original_pos.x, original_pos.y, duration=0.2)
        
        return f"✅ '{best_match['text']}' element par click kar diya gaya (similarity: {best_score:.2f})"
        
    except Exception as e:
        return f"🚫 Error: {str(e)}"


@function_tool()
async def get_clickable_elements() -> str:
    """
    Identifies all clickable/interactive elements on the current screen 
    using OCR and heuristic detection.
    
    Returns:
        str: List of detected clickable elements with their positions
    """
    try:
        # Take screenshot
        screenshot = await asyncio.to_thread(pyautogui.screenshot)
        screenshot_np = __import__('cv2').cvtColor(
            __import__('numpy').array(screenshot), 
            __import__('cv2').COLOR_RGB2BGR
        )
        
        # Run OCR
        import pytesseract
        data = await asyncio.to_thread(
            pytesseract.image_to_data,
            screenshot_np,
            output_type=pytesseract.Output.DICT
        )
        
        # Heuristics for clickable elements
        # Look for text that might be buttons, links, menu items
        clickable = []
        
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if not text:
                continue
            
            # Get position and size
            x, y, w, h = int(data['left'][i]), int(data['top'][i]), int(data['width'][i]), int(data['height'][i])
            
            # Heuristics: reasonable size, not too small/large
            if w < 50 or h < 50 or w > 500 or h > 500:
                continue
            
            # Look for common button/ link patterns
            lower_text = text.lower()
            button_keywords = ['click', 'submit', 'ok', 'cancel', 'login', 'search', 'menu', 'start', 'stop',
                              'next', 'prev', 'home', 'back', 'exit', 'save', 'delete', 'edit', 'copy', 'paste',
                              'yes', 'no', 'run', 'go', 'find', 'view', 'add', 'remove',
                              'settings', 'preferences', 'profile', 'account', 'help', 'about']
            
            is_likely_button = any(keyword in lower_text for keyword in button_keywords)
            
            # Also check if text is standalone (likely a button)
            if is_likely_button or (w > 30 and h > 30 and len(text) > 0):
                center_x = x + w // 2
                center_y = y + h // 2
                clickable.append({
                    'text': text,
                    'position': (center_x, center_y),
                    'size': (w, h),
                    'rank': i + 1
                })
        
        if not clickable:
            return "❌ koi bhi clickable element detect nahi hua. Screen par kuch buttons ya links dikh rahe honge par unka text detect nahi ho paaya."
        
        # Format response
        output = f"🖱️ Screen par {len(clickable)} clickable elements detect hue:\n\n"
        for i, elem in enumerate(clickable[:15], 1):  # Show top 15
            output += f"{i}. '{elem['text']}' at position ({elem['position'][0]}, {elem['position'][1]}) - size {elem['size'][0]}x{elem['size'][1]}\n"
        
        if len(clickable) > 15:
            output += f"... aur {len(clickable) - 15} or elements."
        
        return output
        
    except Exception as e:
        return f"🚫 Error detecting clickable elements: {str(e)}"


@function_tool()
async def click_at_position(x: int, y: int) -> str:
    """
    Clicks at specific screen coordinates.
    
    Args:
        x: X coordinate
        y: Y coordinate
    
    Returns:
        str: Click confirmation
    """
    try:
        # Get original mouse position
        original_pos = await asyncio.to_thread(pyautogui.position)
        
        # Move to and click
        await asyncio.to_thread(pyautogui.moveTo, x, y, duration=0.3)
        await asyncio.to_thread(pyautogui.click())
        
        # Restore mouse position
        await asyncio.to_thread(pyautogui.moveTo, original_pos.x, original_pos.y, duration=0.2)
        
        return f"✅ Click kar diya gaya coordinate par ({x}, {y})"
        
    except Exception as e:
        return f"🚫 Error clicking at position: {str(e)}"


@function_tool()
async def double_click_at_position(x: int, y: int) -> str:
    """
    Double-click at specific screen coordinates.
    
    Args:
        x: X coordinate
        y: Y coordinate
    
    Returns:
        str: Double-click confirmation
    """
    try:
        # Get original mouse position
        original_pos = await asyncio.to_thread(pyautogui.position)
        
        # Move to and double-click
        await asyncio.to_thread(pyautogui.moveTo, x, y, duration=0.3)
        await asyncio.to_thread(pyautogui.doubleClick())
        
        # Restore mouse position
        await asyncio.to_thread(pyautogui.moveTo, original_pos.x, original_pos.y, duration=0.2)
        
        return f"✅ Double-click kar diya gaya coordinate par ({x}, {y})"
        
    except Exception as e:
        return f"🚫 Error double-clicking at position: {str(e)}"