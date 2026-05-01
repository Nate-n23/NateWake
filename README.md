# NateWake 🌙

NateWake is a strictly **offline-first Android sleep journal application**. It's designed for long-term sleep tracking (months or years), helping users understand their personal circadian rhythms, identify optimal sleep cycles, and plan wake-up times without relying on cloud services.

## Features

- **Long-term Sleep Journal:** Log bedtime, wake time, and nocturnal awakenings.
- **Biologically-Aware Analytics:** Calculates the true duration of your sleep cycles (averaging around 90 minutes) based on your personal data history.
- **Smart Predictive Planner:** A *Ridge regression model* continuously learns from your history to suggest the exact moment you should wake up to feel refreshed.
- **Outlier Handling:** Automatically flags statistically unusual nights (via IQR method) or allows manual overriding to ensure your model's accuracy isn't skewed by illnesses or exceptional events.
- **Third-Party Imports:** Easily import your historical data from *Sleep as Android* or *Sleep Cycle* via CSV.
- **Full Data Ownership:** All data is stored in a structured, local SQLite database. Export your records instantly to CSV, JSON, or direct SQLite backups.

## Tech Stack

NateWake is a pure Python project built for Android deployment:

- **UI Framework**: [Kivy 2.3.0](https://kivy.org/) and [KivyMD 1.2.0](https://kivymd.readthedocs.io/)
- **Data Science Engine**: `pandas` and `numpy` for data manipulation.
- **Machine Learning**: `scikit-learn` (Ridge regression) and `joblib` for persisting the model directly to the filesystem.
- **Database**: Standard Python `sqlite3` driver with a built-in migration system.

---

## 🛠 Project Architecture

The architecture isolates Kivy UI logic from the data science components to ensure pure functions can be perfectly unit tested:

*   **`config.py`**: Centralized configuration and biological thresholds (e.g., minimum cycle length, outlier fences, Ridge model learning thresholds). No magic numbers in the UI.
*   **`models.py`**: Clean, standard Python `dataclasses` defining entities like `Nuit` and `StatsDescriptives`.
*   **`analytics.py`**: A stateless engine that implements cycle calculations, Tukey's fences (IQR) for outliers, and the machine learning model.
*   **`screens/`**: UI implementations relying heavily on KivyMD's Material Design principles.

## 🚀 Running Locally (Desktop)

NateWake includes a development script to orchestrate the environment quickly on Linux systems.

```bash
# 1. Provide execution rights
chmod +x setup.sh

# 2. Run the bootstrap script
./setup.sh
```

The script will automatically set up a Python 3.12 virtual environment, install Kivy dependencies including OS libraries, and trigger the pytest suite.

To boot the app:
```bash
source .venv/bin/activate
python main.py
```

## 🧪 Testing

The logic engine takes no graphical dependencies, meaning testing is extremely fast. The application features 47 rigorous pytests assuring statistical correctness and bounds logic.

```bash
source .venv/bin/activate
pytest tests/test_analytics.py -v
```

## 📱 Building for Android

NateWake bundles a pre-configured `buildozer.spec` file. 
You will need to install the system prerequisites for Buildozer:

```bash
pip install buildozer
sudo apt-get install -y git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config zlib1g-dev \
  libncurses5-dev libssl-dev

# Build a debug APK:
buildozer android debug

# Build, deploy directly to USB-connected device, and read logs:
buildozer android debug deploy run logcat
```
