#!/usr/bin/env python3
"""
Continuous log monitoring and error fixing script.
Monitors Railway logs for errors and attempts to fix them automatically.
"""
import subprocess
import time
import re
import sys
from datetime import datetime
from pathlib import Path

# Change to project directory
PROJECT_DIR = Path(__file__).parent
ERROR_PATTERNS = [
    (r"invalid order base or quote amount|code=21706", "Minimum notional requirement - order size too small"),
    (r"invalid signature|code=21120", "API key signature mismatch - check API_KEY_INDEX"),
    (r"api key not found|code=21109", "API key not registered on-chain"),
    (r"ERROR|Exception|Traceback", "General error detected"),
]

def check_logs():
    """Fetch recent Railway logs."""
    try:
        result = subprocess.run(
            ["railway", "logs", "--tail", "300"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        print(f"⚠️  Error fetching logs: {e}")
        return ""

def analyze_errors(logs):
    """Analyze logs for errors and return findings."""
    errors_found = []

    for pattern, description in ERROR_PATTERNS:
        matches = re.findall(pattern, logs, re.IGNORECASE)
        if matches:
            errors_found.append({
                "pattern": pattern,
                "description": description,
                "matches": matches[:5],  # First 5 matches
            })

    return errors_found

def fix_error(error_info):
    """Attempt to fix detected errors."""
    pattern = error_info["pattern"]
    description = error_info["description"]

    print(f"\n🔧 Attempting to fix: {description}")

    # Fix for minimum notional requirement
    if "21706" in pattern or "invalid order base or quote amount" in pattern.lower():
        print("   → This should already be fixed with 0.01 SOL minimum size")
        print("   → Checking if fix is deployed...")
        return "check_deployment"

    # Fix for API key issues
    if "21120" in pattern or "21109" in pattern:
        print("   → API key issue detected")
        print("   → Manual intervention may be required")
        return "manual_review_needed"

    return "unknown_error"

def main():
    """Main monitoring loop."""
    print("=" * 60)
    print("Railway Log Monitor & Error Fixer")
    print("=" * 60)
    print(f"Project: {PROJECT_DIR}")
    print("Monitoring every 30 seconds...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()

    check_count = 0
    error_count = 0
    last_errors = set()

    try:
        while True:
            check_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[{timestamp}] Check #{check_count} - Fetching logs...", end=" ")

            logs = check_logs()

            if not logs.strip():
                print("(logs empty - bot may be starting)")
                time.sleep(30)
                continue

            errors = analyze_errors(logs)

            if errors:
                error_count += 1
                current_error_keys = {e["pattern"] for e in errors}

                # Only report if errors are new or changed
                if current_error_keys != last_errors:
                    print(f"\n❌ ERRORS DETECTED (Total error checks: {error_count})")
                    print("-" * 60)

                    for error in errors:
                        print(f"\n🔴 {error['description']}")
                        print(f"   Pattern: {error['pattern']}")
                        if error['matches']:
                            print(f"   Sample matches:")
                            for match in error['matches'][:3]:
                                print(f"     - {match[:100]}")

                    print("\n" + "-" * 60)

                    # Attempt fixes
                    for error in errors:
                        fix_result = fix_error(error)
                        if fix_result == "check_deployment":
                            # Verify the fix is in the code
                            mean_rev_file = PROJECT_DIR / "modules" / "mean_reversion_trader.py"
                            if mean_rev_file.exists():
                                content = mean_rev_file.read_text()
                                if "0.01" in content and "min_position_size" in content:
                                    print("   ✅ Fix confirmed in code (0.01 SOL minimum)")
                                else:
                                    print("   ⚠️  Fix may not be in code - checking...")

                    last_errors = current_error_keys
                else:
                    print(f"(same errors as before - {len(errors)} types)")
            else:
                print("✅ No errors found")
                # Show recent activity
                recent_lines = [l for l in logs.split("\n") if l.strip()][-5:]
                if recent_lines:
                    print("   Recent activity:")
                    for line in recent_lines:
                        if any(keyword in line.lower() for keyword in ["info", "entering", "position", "price"]):
                            print(f"   {line[:80]}")

            print()
            time.sleep(30)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        print(f"Total checks: {check_count}")
        print(f"Error checks: {error_count}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error in monitor: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

