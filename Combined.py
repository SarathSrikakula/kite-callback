import os
import subprocess
import sys
import time

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
]


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
  run_pipeline()