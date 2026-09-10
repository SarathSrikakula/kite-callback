import os
import subprocess
import sys
import time
import time
from datetime import datetime
import pytz


def wait_until_target_time(target_hour=13, target_minute=30):
  """Pauses script execution until the target time in Indian Standard Time (IST)."""
  ist = pytz.timezone("Asia/Kolkata")

  while True:
    now_ist = datetime.now(ist)

    # Define today's target time in IST
    target_time = now_ist.replace(
        hour=target_hour, minute=target_minute, second=0, microsecond=0
    )

    # If 1:30 PM IST has already passed today, set target to 1:30 PM tomorrow
    if now_ist >= target_time:
      print(f"1:30 PM IST for today has already passed.")
      # Move target_time forward by 1 day
      target_time = target_time.replace(day=now_ist.day + 1)

    time_to_wait = (target_time - now_ist).total_seconds()

    print(
        f"Current Time (IST): {now_ist.strftime('%Y-%m-%d %I:%M:%S %p %Z')}"
    )
    print(
        f"Scheduled Start   : {target_time.strftime('%Y-%m-%d %I:%M:%S %p %Z')}"
    )
    print(
        f"Waiting for {time_to_wait / 3600:.2f} hours ({int(time_to_wait)} seconds)..."
    )

    # Sleep until the scheduled target time
    time.sleep(time_to_wait)
    break




# ===================================================================
# PIPELINE CONFIGURATION
# Set True to run, False to exclude/skip a step
# ===================================================================
PIPELINE_STEPS = [
    {"name": "Fetch", "file": "Fetch.py", "run": True},
    
    {"name": "Curve", "file": "curve.py", "run": True},
    {"name": "Draw", "file": "Draw.py", "run": True},
    {"name": "Fetch India", "file": "fetchIndia.py", "run": True},
    {"name": "Curve India", "file": "curveIndia.py", "run": True},
    {"name": "Draw India", "file": "DrawIndia.py", "run": True},
    {"name": "Draw India1", "file": "DrawIndia1.py", "run": True},
    {"name": "Draw India1", "file": "DrawUSA1.py", "run": True},
]
SHUTDOWN_AFTER_RUN = True
SHUTDOWN_DELAY_SECONDS = 60

# ===================================================================
# PIPELINE EXECUTION ENGINE
# ===================================================================
def run_pipeline():
  print("================ 🏁 STARTING PIPELINE 🏁 ================\n")
  start_total = time.time()
  python_exe = sys.executable  # Uses your PyCharm environment interpreter

  completed = 0
  skipped = 0

  for idx, step in enumerate(PIPELINE_STEPS, 1):
    step_name = step["name"]
    script_file = step["file"]
    should_run = step["run"]

    print("-" * 60)
    print(f"📍 [{idx}/{len(PIPELINE_STEPS)}] Step: {step_name} ({script_file})")

    # Exclude / Skip logic
    if not should_run:
      print("   ⏩ Status: SKIPPED (Excluded in configuration)")
      skipped += 1
      continue

    # Verify file exists before running
    if not os.path.exists(script_file):
      print(f"   ❌ Error: File '{script_file}' not found in current folder.")
      print("   ⛔ Stopping pipeline.")
      break

    print("   🚀 Status: RUNNING...\n")
    step_start = time.time()

    # Runs script and streams all console prints in real-time
    result = subprocess.run([python_exe, script_file])

    step_elapsed = round(time.time() - step_start, 2)

    if result.returncode == 0:
      print(f"\n   ✅ Completed '{step_name}' in {step_elapsed}s")
      completed += 1
    else:
      print(
          f"\n   ❌ FAILED '{step_name}' (Exit Code: {result.returncode})."
          " Stopping pipeline."
      )
      break

  total_elapsed = round(time.time() - start_total, 2)
  print("\n========================================================")
  print(
      f"🏁 PIPELINE SUMMARY: {completed} Completed | {skipped} Skipped |"
      f" Total Time: {total_elapsed}s"
  )
  print("========================================================")


if __name__ == "__main__":
  #wait_until_target_time(target_hour=13, target_minute=30)
  run_pipeline()

  if SHUTDOWN_AFTER_RUN:
      os.system(f"shutdown /s /t {SHUTDOWN_DELAY_SECONDS}")