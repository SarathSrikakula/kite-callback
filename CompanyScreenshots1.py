import pyautogui
import sys
import time

# --- 1. CRITICAL CONFIG ---
# Disable built-in failsafe so we can use (0,0) as a trigger zone
pyautogui.FAILSAFE = False

# Screen Dimensions
SW, SH = pyautogui.size()

# Coordinates from your setup
COORDS = {
    "Edit_Image": (40, 27),
    "Mark_Up": (997, 107),
    "Select_Marker": (835, 960),
    "Dark_Purple": (862, 764),
    "Magenta": (962, 761),
    "Save_Options": (1650, 106),
    "Save": (1616, 200)
}

# Thresholds for corners (60x60 pixel box)
ZONE_SIZE = 60
SAFE_X_LIMIT = SW - ZONE_SIZE
SAFE_Y_LIMIT = SH - ZONE_SIZE

# Workflow States
state = {"PURPLE": "SETUP", "MAGENTA": "SETUP"}

# --- 2. TIMED SEQUENCES ---
# Format: (Action_Name, Seconds_To_Wait_After_Click)
PURPLE_SETUP_FLOW = [
    ("Edit_Image", 1.5),
    ("Mark_Up", 1.0),
    ("Select_Marker", 0.5),
    ("Dark_Purple", 1.0)
]

MAGENTA_SETUP_FLOW = [
    ("Edit_Image",1.5) ,
    ("Mark_Up", 1.0),
    ("Select_Marker", 0.5),
    ("Magenta", 1.0)
]

SAVE_FLOW = [
    ("Save_Options", 1.2),
    ("Save", 1.0)
]


# --- 3. SAFETY FUNCTIONS ---
def check_failsafe():
    """Emergency Stop: Slam mouse to the BOTTOM-RIGHT corner."""
    x, y = pyautogui.position()
    if x >= SAFE_X_LIMIT and y >= SAFE_Y_LIMIT:
        print("\n🚨 EMERGENCY STOP: Mouse at Bottom-Right. Exiting script.")
        sys.exit()


def run_timed_sequence(steps):
    """Executes a list of clicks with specific delays and safety checks."""
    for action, delay in steps:
        check_failsafe()  # Check before move
        pos = COORDS[action]
        pyautogui.moveTo(pos[0], pos[1], duration=0.4)

        check_failsafe()  # Check before click
        pyautogui.click()

        print(f"  -> {action} done. Waiting {delay}s...")
        time.sleep(delay)


# --- 4. MAIN MONITORING ENGINE ---
def monitor_logic():
    global state
    print("--- 🚀 Trading Screenshot Automator Active ---")
    print(f"1. [TOP-LEFT]    -> Purple Flow (Next: {state['PURPLE']})")
    print(f"2. [BOTTOM-LEFT] -> Magenta Flow (Next: {state['MAGENTA']})")
    print(f"3. [BOTTOM-RIGHT]-> EMERGENCY STOP")

    while True:
        try:
            check_failsafe()
            x, y = pyautogui.position()

            # --- ZONE: TOP-LEFT (PURPLE) ---
            if x < ZONE_SIZE and y < ZONE_SIZE:
                print(f"\n[!] Triggering Purple {state['PURPLE']}...")
                time.sleep(1.2)  # Hold requirement

                check_failsafe()
                if pyautogui.position().x < ZONE_SIZE and pyautogui.position().y < ZONE_SIZE:
                    if state["PURPLE"] == "SETUP":
                        run_timed_sequence(PURPLE_SETUP_FLOW)
                        state["PURPLE"] = "SAVE"
                    else:
                        run_timed_sequence(SAVE_FLOW)
                        state["PURPLE"] = "SETUP"

                    # Move to center and wait to prevent double-trigger
                    pyautogui.moveTo(SW // 2, SH // 2)
                    time.sleep(2)

            # --- ZONE: BOTTOM-LEFT (MAGENTA) ---
            elif x < ZONE_SIZE and y > SAFE_Y_LIMIT:
                print(f"\n[!] Triggering Magenta {state['MAGENTA']}...")
                time.sleep(1.2)  # Hold requirement

                check_failsafe()
                if pyautogui.position().x < ZONE_SIZE and pyautogui.position().y > SAFE_Y_LIMIT:
                    if state["MAGENTA"] == "SETUP":
                        run_timed_sequence(MAGENTA_SETUP_FLOW)
                        state["MAGENTA"] = "SAVE"
                    else:
                        run_timed_sequence(SAVE_FLOW)
                        state["MAGENTA"] = "SETUP"

                    pyautogui.moveTo(SW // 2, SH // 2)
                    time.sleep(2)

            # Live status update in terminal
            print(f"\rP:{state['PURPLE']} M:{state['MAGENTA']} | Mouse: {x},{y}   ", end='')
            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nManual Exit.")
            break


if __name__ == "__main__":
    monitor_logic()