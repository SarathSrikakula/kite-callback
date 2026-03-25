import sys

import pyautogui
import time
import os

# --- COORDINATES ---
EXCEL_APP = (1158, 1054)
EDGE_APP = (1099, 1055)
SEARCH_BOX = (246, 200)
OPEN_GRAPH = (438, 292)

# --- SETTINGS ---
ITERATIONS = 5  # Set this to the number of companies in your Excel list
SAVE_DIR = "Company_Charts"
if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)

# Get your screen resolution dynamically
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
# Define the "Kill Zone" (e.g., within 5 pixels of the bottom)
BOTTOM_THRESHOLD = SCREEN_HEIGHT - 5
def check_failsafe():
    """Checks if mouse is at the bottom of the screen and stops the script."""
    current_mouse_y = pyautogui.position().y
    if current_mouse_y >= BOTTOM_THRESHOLD:
        print("\n🚨 EMERGENCY STOP: Mouse detected at bottom edge. Exiting script.")
        # sys.exit() is the cleanest way to kill the script
        sys.exit()
def start_macro():
    print(f">>> Macro starting. Ensure Excel and Edge are open. Loops: {ITERATIONS}")
    time.sleep(3)

    for i in range(ITERATIONS):
        print(f"Loop {i+1} of {ITERATIONS}...")
        check_failsafe()
        # 1. GO TO EXCEL & GET DATA
        pyautogui.click(EXCEL_APP)
        time.sleep(0.5)
        pyautogui.press('up')    # Move to the next stock symbol
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'c') # Copy the symbol
        time.sleep(0.5)

        check_failsafe()
        # 2. GO TO EDGE & SEARCH
        pyautogui.click(EDGE_APP)
        time.sleep(0.8)
        pyautogui.click(SEARCH_BOX)

        # 2. PERFORM THE MOVEMENT
        # We move from the current position (Search Box) to the Open Graph button
        # 'duration' makes the mouse move smoothly over 0.6 seconds instead of teleporting
        pyautogui.moveTo(OPEN_GRAPH[0], OPEN_GRAPH[1], duration=0.6)

        # 3. CLICK THE TARGET
        pyautogui.click()


        time.sleep(0.5)
        # Clear existing text and paste
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(1)

        check_failsafe()
        # 3. OPEN GRAPH & SCREENSHOT
        pyautogui.click(OPEN_GRAPH)
        print("Waiting for chart to load...")
        time.sleep(7) # Adjust based on your internet speed

        check_failsafe()
        # Save with a timestamp or index
        file_name = f"chart_{i+1}_{int(time.time())}.png"
        save_path = os.path.join(SAVE_DIR, file_name)
        pyautogui.screenshot(save_path)
        print(f"✅ Saved: {save_path}")

        # Optional: Press 'V' to clear the view if needed
        # pyautogui.press('v')

    print(">>> Finished all iterations.")

if __name__ == "__main__":
    start_macro()