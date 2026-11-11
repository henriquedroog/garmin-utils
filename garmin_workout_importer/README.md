# Garmin Connect Workout Importer

A Python tool to automatically upload structured workout definitions into your Garmin Connect account using environment variables.

---

## 📋 Setup Instructions (macOS)

### 1. Prerequisites & Virtual Environment
Ensure you have Python 3 installed. Open your Terminal and set up your virtual environment:

```bash
# Clone/download this folder and navigate into it
cd garmin_workout_importer

# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install required dependencies
pip install garminconnect
```

---

## 🔑 2. Set Environment Variables & Run

Export your Garmin Connect credentials in your terminal session, then execute the script:

```bash
# Export your Garmin account credentials
export GARMIN_EMAIL="your_email@example.com"
export GARMIN_PASSWORD="your_password"

# Run the importer script
python garmin_workout_importer.py
```

> **Tip:** The environment variables exist only for your active Terminal session and won't leak your credentials into your code or git history.

---

## 📝 3. Customizing Workouts (`workouts.json`)

Edit `workouts.json` to define your workouts. The script supports multiple workouts in a single run:

```json
[
  {
    "workout_name": "Endurance #1 - Cruise Intervals",
    "sport_type": "running",
    "warmup_seconds": 1200,
    "repeats": 5,
    "work_seconds": 300,
    "rest_seconds": 60,
    "cooldown_seconds": 60
  }
]
```

---

## 🚀 4. Syncing to Watch

Once executed, open **Garmin Connect** on your phone or web browser. Your newly created workouts will be visible under **Training & Planning > Workouts** and will automatically transfer to your watch during your next sync!
