# National Weather Intelligence Platform 🌦️⚡

An AI-powered multi-source weather monitoring, verification, and real-time event intelligence platform for India.

---

## 🚀 How to Run in Visual Studio Code (VS Code)

### Prerequisites
1. **Python 3.10+**: Ensure Python is installed and added to PATH.
2. **PostgreSQL**: PostgreSQL service running locally on port `5432` with database `national_weather`.

---

### Step-by-Step Setup & Run in VS Code

#### 1. Open Project in VS Code
Open VS Code and navigate to the project directory:
```bash
code .
```
*(Or in VS Code: `File -> Open Folder...` and select `NationalWeatherPlatform`)*

#### 2. Environment Variables (.env)
The `.env` file is already pre-configured for your local workspace. If missing, copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

#### 3. Run the Application (One-Click Options in VS Code)

* **Option A: F5 Debug / Launch (Recommended)**
  1. Open the **Run and Debug** panel in VS Code (`Ctrl+Shift+D` or click the play icon on the left sidebar).
  2. Select **`🚀 Run Weather Platform (Flask + SocketIO)`** from the dropdown menu at the top.
  3. Press **`F5`** (or click the green Play button).
  4. Open your browser at: **`http://localhost:5000`**

* **Option B: VS Code Task Runner**
  1. Press `Ctrl+Shift+B` (or `Ctrl+Shift+P` -> type `Tasks: Run Build Task`).
  2. Select **`3. Run Weather Platform Server`**.

* **Option C: Integrated Terminal**
  Open VS Code integrated terminal (`Ctrl+\``) and run:
  ```powershell
  python app.py
  ```

---

## 🧪 Running Unit Tests in VS Code

* **Via F5 Debugger**:
  Select **`🧪 Run All Unit Tests`** in the Run & Debug menu and press `F5`.

* **Via Terminal**:
  ```powershell
  python -m unittest discover -s . -p "test_*.py"
  ```

* **Via VS Code Testing Panel**:
  Open the **Testing** tab (`flask` icon on left sidebar) to view and run individual test cases interactively.

---

## 🔐 Default Access Credentials

| User Role | Username | Password | Access Rights |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full control center, report verification, audit logs |
| **Data Analyst** | `analyst` | `analyst123` | Analytics, exports, verification review |
| **Public User** | *None required* | *N/A* | View dashboard, live map, submit reports |

---

## 📌 Features Overview
- **Live India Map**: Interactive Leaflet.js weather & event visualization.
- **AI Event Classification**: Automatic classification of weather reports into severe categories.
- **Verification Engine**: AI cross-verification against actual meteorological observations.
- **Duplicate Detection**: Jaccard & TF-IDF similarity scoring.
- **Real-Time Stream**: SocketIO live updates and severe weather toast notifications.
- **Data Export Center**: Parameterized CSV/JSON exports and executive intelligence summaries.
