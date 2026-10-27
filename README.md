# College Event Registration System

A beginner-friendly MongoDB project using Python, PyMongo, and Streamlit.

## Features
- **Role-Based Portals**:
  - **🎓 Participant Portal**:
    - Browse upcoming events with live capacity meters
    - Register for events with validation and duplicate prevention
    - "My Registrations" view for searching bookings by roll number and self-canceling
    - Event Schedule timeline
  - **🛠️ Admin Portal**:
    - Secure administrator login (`admin` / `admin123` or configurable via environment variables)
    - Admin analytics dashboard (seat occupancy %, registration volume, capacity breakdown)
    - Add, edit, and delete events with real-time sync across registrations
    - View full student participant roster and export to CSV
    - Admin-level registration lookup and cancellation
- **MongoDB Concurrency**:
  - Atomic seat decrement/increment preventing race-condition overbooking
  - Unique compound indexing preventing duplicate registrations per student

## Requirements
- Python 3.10 or newer
- MongoDB Community Server running locally OR a MongoDB Atlas connection string
- Optional: MongoDB Compass to inspect the database

## Windows setup

1. Install Python from https://www.python.org/downloads/ (select "Add Python to PATH").
2. Install MongoDB Community Server from https://www.mongodb.com/try/download/community.
   During installation, choose to run MongoDB as a Windows service.
3. Optional: install MongoDB Compass from https://www.mongodb.com/try/download/compass.
4. Extract this project ZIP and open Command Prompt or PowerShell in the extracted folder.
5. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt instead:

   ```bat
   .venv\Scripts\activate.bat
   ```

6. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

7. Start MongoDB if it is not already running. If installed as a Windows service, it may already be running.
8. Launch the app:

   ```powershell
   streamlit run app.py
   ```

9. Your browser should open at `http://localhost:8501`.

The database and collections are created automatically when the app first connects and creates its indexes.

## MongoDB Atlas instead of local MongoDB

Set the environment variable `MONGODB_URI` to your Atlas connection string before launching Streamlit.

PowerShell example (for this terminal session only):

```powershell
$env:MONGODB_URI="mongodb+srv://USERNAME:PASSWORD@YOUR-CLUSTER.mongodb.net/?retryWrites=true&w=majority"
streamlit run app.py
```

Replace the placeholders with your Atlas details. Do not publish your URI or password. In Atlas, create a database user and allow your current IP address in Network Access.

## MongoDB structure

Database: `CollegeEventDB`

Collections:
- `events`: event_id, name, category, event_date, venue, total_seats, registered_count, description
- `registrations`: registration_id, event_id, event_name, student_name, roll_no, email, department

The `event_id` field links registrations to events. A unique compound index on `roll_no` and `event_id` prevents duplicate registrations.

## Demo steps
1. Open Manage Events and add an event with a capacity of 2.
2. Open Browse & Register and register two different students.
3. Try registering a third student; the app should say the event is full.
4. Try registering the same roll number for the same event again; the app should prevent the duplicate.
5. Open Participants and view/download the list.
6. Cancel a registration and confirm that one seat becomes available.
7. Open MongoDB Compass, connect to `mongodb://localhost:27017`, and inspect `CollegeEventDB`.

## Notes
- This is a learning/demo project, not a production-ready registration service.
- For a public deployment, add authentication and authorization, protect personal information, and review transaction handling and security.
