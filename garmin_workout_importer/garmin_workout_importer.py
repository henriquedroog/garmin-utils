import json
import os
import sys

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# Read credentials from environment variables
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")
# Tokens are cached here after the first login, so later runs skip the
# full login (and MFA) and are less likely to hit Garmin's rate limits.
TOKEN_STORE = os.getenv("GARMINTOKENS", "~/.garminconnect")
JSON_FILE = "workouts.json"

# Garmin workout sport type IDs (from /workout-service/workout/types)
SPORT_TYPE_IDS = {
    "running": 1,
    "cycling": 2,
    "other": 3,
    "swimming": 4,
    "strength_training": 5,
    "cardio_training": 6,
    "yoga": 7,
    "pilates": 8,
    "hiit": 9,
    "multi_sport": 10,
    "mobility": 11,
}

TIME_CONDITION = {"conditionTypeId": 2, "conditionTypeKey": "time"}
ITERATIONS_CONDITION = {"conditionTypeId": 7, "conditionTypeKey": "iterations"}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}


def time_step(step_order: int, step_type_id: int, step_type_key: str, seconds: int) -> dict:
    """A single timed step (warmup, interval, recovery, cooldown)."""
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": step_type_id, "stepTypeKey": step_type_key},
        "endCondition": TIME_CONDITION,
        "endConditionValue": seconds,
        "targetType": NO_TARGET,
    }


def build_garmin_payload(workout_data: dict) -> dict:
    """Converts a simplified workout dictionary into Garmin's expected JSON payload structure."""
    sport_key = workout_data.get("sport_type", "running").lower()
    if sport_key not in SPORT_TYPE_IDS:
        raise ValueError(
            "Unknown sport_type '" + sport_key + "'. Use one of: " + ", ".join(SPORT_TYPE_IDS)
        )
    sport_type = {"sportTypeId": SPORT_TYPE_IDS[sport_key], "sportTypeKey": sport_key}

    warmup_sec = workout_data.get("warmup_seconds", 0)
    repeats = workout_data.get("repeats", 1)
    work_sec = workout_data.get("work_seconds", 300)
    rest_sec = workout_data.get("rest_seconds", 60)
    cooldown_sec = workout_data.get("cooldown_seconds", 0)

    steps = []
    step_order = 1

    # Optional Warmup Block
    if warmup_sec > 0:
        steps.append(time_step(step_order, 1, "warmup", warmup_sec))
        step_order += 1

    # Main Repeats Block (Work + Rest)
    repeat_order = step_order
    steps.append(
        {
            "type": "RepeatGroupDTO",
            "stepOrder": repeat_order,
            "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
            "numberOfIterations": repeats,
            "endCondition": ITERATIONS_CONDITION,
            "endConditionValue": repeats,
            "smartRepeat": False,
            "workoutSteps": [
                time_step(repeat_order + 1, 3, "interval", work_sec),
                time_step(repeat_order + 2, 4, "recovery", rest_sec),
            ],
        }
    )
    step_order = repeat_order + 3

    # Optional Cooldown Block
    if cooldown_sec > 0:
        steps.append(time_step(step_order, 2, "cooldown", cooldown_sec))

    return {
        "workoutName": workout_data["workout_name"],
        "sportType": sport_type,
        "estimatedDurationInSecs": warmup_sec + repeats * (work_sec + rest_sec) + cooldown_sec,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": sport_type,
                "workoutSteps": steps,
            }
        ],
    }


def get_existing_workout_names(client: Garmin) -> set:
    """Return the names of all workouts already in the account."""
    names = set()
    start = 0
    page_size = 100
    while True:
        page = client.get_workouts(start, page_size, my_workouts_only=True)
        names.update(w.get("workoutName") for w in page)
        if len(page) < page_size:
            return names
        start += page_size


def main():
    has_tokens = os.path.isdir(os.path.expanduser(TOKEN_STORE))
    if not has_tokens and (not GARMIN_EMAIL or not GARMIN_PASSWORD):
        print("Error: no saved login found, so GARMIN_EMAIL and GARMIN_PASSWORD must be set.")
        print("Usage on macOS:")
        print("  export GARMIN_EMAIL='your_email@example.com'")
        print("  export GARMIN_PASSWORD='your_password'")
        print("  python garmin_workout_importer.py")
        sys.exit(1)

    if not os.path.exists(JSON_FILE):
        print("Error: " + JSON_FILE + " not found.")
        sys.exit(1)

    # Load workouts from JSON
    with open(JSON_FILE, "r") as f:
        try:
            workouts = json.load(f)
        except json.JSONDecodeError as e:
            print("Error reading JSON file: " + str(e))
            sys.exit(1)

    # Authenticate with Garmin Connect
    print("Logging into Garmin Connect...")
    try:
        client = Garmin(
            GARMIN_EMAIL,
            GARMIN_PASSWORD,
            prompt_mfa=lambda: input("Enter the MFA code Garmin sent you: ").strip(),
        )
        client.login(tokenstore=TOKEN_STORE)
        print("Login successful!")
    except GarminConnectTooManyRequestsError as err:
        print("Garmin is rate limiting logins, please wait a while and try again: " + str(err))
        sys.exit(1)
    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
    ) as err:
        print("Authentication failed: " + str(err))
        sys.exit(1)

    # Fetch existing workout names so we don't create duplicates
    try:
        existing_names = get_existing_workout_names(client)
    except Exception as e:
        print("Could not fetch existing workouts, aborting to avoid duplicates: " + str(e))
        sys.exit(1)

    # Process and upload workouts
    for workout in workouts:
        workout_name = workout.get("workout_name", "Untitled Workout")
        if workout_name in existing_names:
            print("Skipping: '" + workout_name + "' already exists in Garmin Connect.")
            continue
        print("Uploading: '" + workout_name + "'...")

        try:
            payload = build_garmin_payload(workout)
            response = client.upload_workout(payload)
            workout_id = response.get("workoutId", "Unknown")
            print("  Success! Created Workout ID: " + str(workout_id))
            existing_names.add(workout_name)
        except Exception as e:
            print("  Failed to upload '" + workout_name + "': " + str(e))


if __name__ == "__main__":
    main()
