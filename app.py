import os
import io
import csv
from datetime import date
from uuid import uuid4

import streamlit as st
from pymongo import MongoClient, ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

# -------------------- CONFIG & DATABASE --------------------
st.set_page_config(page_title="College Event Portal", page_icon="🎓", layout="wide")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
CATEGORIES = ["Technical", "Cultural", "Sports", "Workshop", "Seminar", "Other"]

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

@st.cache_resource
def get_database():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client["CollegeEventDB"]
    db.events.create_index([("event_id", ASCENDING)], unique=True)
    db.registrations.create_index([("roll_no", ASCENDING), ("event_id", ASCENDING)], unique=True)
    db.registrations.create_index([("event_id", ASCENDING)])
    db.registrations.create_index([("roll_no", ASCENDING)])
    return db

try:
    db = get_database()
    events = db["events"]
    registrations = db["registrations"]
    db_error = None
except Exception as exc:
    db = events = registrations = None
    db_error = str(exc)

# -------------------- HELPER FUNCTIONS --------------------
def seats_left(event):
    return max(0, int(event.get("total_seats", 0)) - int(event.get("registered_count", 0)))

def register_student(event_id, student_name, roll_no, email, department):
    event = events.find_one_and_update(
        {"event_id": event_id, "$expr": {"$lt": ["$registered_count", "$total_seats"]}},
        {"$inc": {"registered_count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not event:
        return False, "This event is full or no longer available."

    try:
        registrations.insert_one({
            "registration_id": str(uuid4()
            ),
            "event_id": event_id,
            "event_name": event["name"],
            "student_name": student_name.strip(),
            "roll_no": roll_no.strip().upper(),
            "email": email.strip().lower(),
            "department": department.strip(),
        })
        return True, "Registration successful!"
    except DuplicateKeyError:
        events.update_one({"event_id": event_id}, {"$inc": {"registered_count": -1}})
        return False, "This roll number is already registered for this event."
    except Exception:
        events.update_one({"event_id": event_id}, {"$inc": {"registered_count": -1}})
        raise

def cancel_registration(registration_id):
    reg = registrations.find_one({"registration_id": registration_id})
    if reg and registrations.delete_one({"registration_id": registration_id}).deleted_count:
        events.update_one({"event_id": reg["event_id"], "registered_count": {"$gt": 0}}, {"$inc": {"registered_count": -1}})
        return True
    return False

# -------------------- DATABASE CONNECTION CHECK --------------------
if db_error:
    st.title("🎓 College Event Registration System")
    st.error("⚠️ Could not connect to MongoDB. Ensure MongoDB is running or configure `MONGODB_URI`.")
    with st.expander("Connection technical details"):
        st.code(db_error)
    st.stop()

# -------------------- SIDEBAR ROLE SELECTOR --------------------
st.sidebar.title("Navigation")
portal = st.sidebar.radio("Select Portal", ["🎓 Participant Portal", "🛠️ Admin Portal"])
st.sidebar.divider()

# ==========================================================
#                   PARTICIPANT / STUDENT PORTAL
# ==========================================================
if portal == "🎓 Participant Portal":
    st.title("🎓 Student Event Portal")
    st.caption("Discover college events, register for sessions, and track your bookings.")

    p_page = st.sidebar.radio("Participant Menu", ["🎫 Browse & Register", "📜 My Registrations", "📅 Event Schedule"])
    st.sidebar.divider()
    st.sidebar.caption("Connected to CollegeEventDB")

    all_events = list(events.find().sort("event_date", ASCENDING))

    # --- BROWSE & REGISTER ---
    if p_page == "🎫 Browse & Register":
        st.subheader("Explore Upcoming Events")
        if not all_events:
            st.info("No events are currently scheduled. Please check back later!")
        else:
            event_map = {f"{e['name']} | {e.get('event_date', 'TBA')} ({seats_left(e)} seats left)": e["event_id"] for e in all_events}
            selected_label = st.selectbox("Select an Event", list(event_map.keys()), key="p_select_event")
            ev = events.find_one({"event_id": event_map[selected_label]})

            if ev:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    col1.markdown(f"## {ev['name']}")
                    col1.write(f"🏷️ **Category:** {ev.get('category', 'Other')}  ·  📅 **Date:** {ev.get('event_date', 'TBA')}  ·  📍 **Venue:** {ev.get('venue', 'TBA')}")
                    if ev.get("description"):
                        col1.write(f"**About:** {ev['description']}")
                    
                    left_seats = seats_left(ev)
                    col2.metric("Available Seats", left_seats)
                    pct = min(1.0, ev.get("registered_count", 0) / max(1, ev.get("total_seats", 1)))
                    col2.progress(pct, text=f"{ev.get('registered_count', 0)} / {ev.get('total_seats', 0)} booked")

                st.subheader("Register for this Event")
                if left_seats <= 0:
                    st.warning("⚠️ This event has reached full capacity. Registrations are closed.")
                else:
                    with st.form("student_registration_form", clear_on_submit=True):
                        col_a, col_b = st.columns(2)
                        name = col_a.text_input("Full Name *", placeholder="e.g. Jane Doe")
                        roll_no = col_b.text_input("Roll Number *", placeholder="e.g. 21CS101")
                        email = col_a.text_input("College Email *", placeholder="e.g. jane@college.edu")
                        dept = col_b.text_input("Department / Branch *", placeholder="e.g. Computer Science")
                        
                        submit = st.form_submit_button("Confirm Registration", type="primary")
                        if submit:
                            if not all([name.strip(), roll_no.strip(), email.strip(), dept.strip()]):
                                st.error("Please fill in all required fields.")
                            elif "@" not in email or "." not in email.split("@")[-1]:
                                st.error("Please provide a valid email address.")
                            else:
                                try:
                                    ok, msg = register_student(ev["event_id"], name, roll_no, email, dept)
                                    if ok:
                                        st.success(f"🎉 {msg} See you at {ev['name']}!")
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                except PyMongoError as err:
                                    st.error(f"Database error: {err}")

    # --- MY REGISTRATIONS ---
    elif p_page == "📜 My Registrations":
        st.subheader("Lookup Your Event Registrations")
        st.write("Enter your roll number to view your registered events or cancel a ticket.")
        
        search_roll = st.text_input("Student Roll Number", placeholder="e.g. 21CS101").strip().upper()
        if search_roll:
            regs = list(registrations.find({"roll_no": search_roll}).sort("event_name", ASCENDING))
            if not regs:
                st.info(f"No active registrations found for roll number `{search_roll}`.")
            else:
                st.success(f"Found {len(regs)} registration(s) for `{search_roll}`")
                for r in regs:
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"### {r.get('event_name', 'Event')}")
                        c1.write(f"👤 **Student Name:** {r.get('student_name')}  ·  🏫 **Department:** {r.get('department')}")
                        c1.write(f"📧 **Email:** {r.get('email')}  ·  🎫 **Pass ID:** `{r.get('registration_id')[:8]}`")
                        
                        if c2.button("Cancel Booking", key=f"p_cancel_{r['registration_id']}", type="secondary"):
                            if cancel_registration(r["registration_id"]):
                                st.success("Registration cancelled and seat released.")
                                st.rerun()
                            else:
                                st.error("Could not cancel registration.")

    # --- EVENT SCHEDULE ---
    elif p_page == "📅 Event Schedule":
        st.subheader("College Events Timeline")
        if not all_events:
            st.info("No events scheduled at the moment.")
        else:
            for ev in all_events:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    c1.markdown(f"### {ev['name']}")
                    c1.caption(ev.get("description", "No description provided."))
                    c2.write(f"📅 **Date:** {ev.get('event_date', 'TBA')}")
                    c2.write(f"📍 **Venue:** {ev.get('venue', 'TBA')}  ·  🏷️ **Category:** {ev.get('category', 'Other')}")
                    c3.metric("Seats Open", seats_left(ev))

# ==========================================================
#                       ADMIN PORTAL
# ==========================================================
else:
    st.title("🛠️ Administrator Portal")

    # Authentication Gate
    if not st.session_state.admin_logged_in:
        st.info("Please log in with administrator credentials to manage events and participants.")
        with st.form("admin_auth_form"):
            user = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Log In as Admin", type="primary")
            if login_btn:
                if user == ADMIN_USER and password == ADMIN_PASS:
                    st.session_state.admin_logged_in = True
                    st.success("Authentication successful!")
                    st.rerun()
                else:
                    st.error("Invalid administrator credentials.")
        st.stop()

    # Logged-in admin sidebar
    st.sidebar.success("Logged in as Admin")
    if st.sidebar.button("Log Out"):
        st.session_state.admin_logged_in = False
        st.rerun()

    admin_page = st.sidebar.radio(
        "Admin Menu",
        ["📊 Dashboard & Stats", "➕ Add New Event", "✏️ Manage & Edit Events", "👥 Participants & Export", "❌ Manage Registrations"]
    )
    st.sidebar.divider()
    st.sidebar.caption("Connected to CollegeEventDB")

    all_events = list(events.find().sort("event_date", ASCENDING))

    # --- ADMIN DASHBOARD ---
    if admin_page == "📊 Dashboard & Stats":
        st.subheader("System Overview")
        total_regs = registrations.count_documents({})
        total_capacity = sum(int(e.get("total_seats", 0)) for e in all_events)
        avail_seats = sum(seats_left(e) for e in all_events)
        occ_rate = round((total_regs / total_capacity * 100), 1) if total_capacity > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Events", len(all_events))
        m2.metric("Total Registrations", total_regs)
        m3.metric("Total Seat Capacity", total_capacity)
        m4.metric("Overall Occupancy", f"{occ_rate}%", delta=f"{avail_seats} seats free")

        st.divider()
        st.subheader("Event Capacity Status")
        if not all_events:
            st.info("No events created yet.")
        else:
            for ev in all_events:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{ev['name']}** ({ev.get('category', 'Other')}) — 📅 {ev.get('event_date', 'TBA')} @ {ev.get('venue', 'TBA')}")
                    pct = min(1.0, ev.get("registered_count", 0) / max(1, ev.get("total_seats", 1)))
                    c1.progress(pct, text=f"{ev.get('registered_count', 0)} of {ev.get('total_seats', 0)} seats booked")
                    c2.metric("Seats Left", seats_left(ev))

    # --- ADD EVENT ---
    elif admin_page == "➕ Add New Event":
        st.subheader("Create a New Event")
        with st.form("admin_create_event", clear_on_submit=True):
            name = st.text_input("Event Name", placeholder="e.g. Annual Tech Symposium")
            category = st.selectbox("Category", CATEGORIES, key="add_event_cat")
            event_date = st.date_input("Event Date", value=date.today(), key="add_event_date")
            venue = st.text_input("Venue", placeholder="e.g. Auditorium Hall B")
            total_seats = st.number_input("Total Capacity", min_value=1, max_value=50000, value=100, step=1)
            description = st.text_area("Event Description")
            submit = st.form_submit_button("Publish Event", type="primary")

            if submit:
                if not name.strip() or not venue.strip():
                    st.error("Event name and venue are required.")
                else:
                    try:
                        events.insert_one({
                            "event_id": str(uuid4()),
                            "name": name.strip(),
                            "category": category,
                            "event_date": event_date.isoformat(),
                            "venue": venue.strip(),
                            "total_seats": int(total_seats),
                            "registered_count": 0,
                            "description": description.strip(),
                        })
                        st.success(f"Event '{name}' created successfully!")
                        st.rerun()
                    except PyMongoError as err:
                        st.error(f"Failed to create event: {err}")

    # --- EDIT & MANAGE EVENTS ---
    elif admin_page == "✏️ Manage & Edit Events":
        st.subheader("Edit or Remove Existing Events")
        if not all_events:
            st.info("No events to manage.")
        else:
            for ev in all_events:
                eid = ev["event_id"]
                with st.expander(f"{ev['name']} — {ev.get('event_date', '')} ({ev.get('registered_count', 0)}/{ev.get('total_seats', 0)} registered)"):
                    with st.form(f"edit_form_{eid}"):
                        new_name = st.text_input("Name", value=ev.get("name", ""), key=f"name_{eid}")
                        cat_idx = CATEGORIES.index(ev.get("category", "Other")) if ev.get("category") in CATEGORIES else 5
                        new_cat = st.selectbox("Category", CATEGORIES, index=cat_idx, key=f"cat_{eid}")
                        try:
                            cur_dt = date.fromisoformat(ev.get("event_date", date.today().isoformat()))
                        except ValueError:
                            cur_dt = date.today()
                        new_dt = st.date_input("Date", value=cur_dt, key=f"date_{eid}")
                        new_venue = st.text_input("Venue", value=ev.get("venue", ""), key=f"venue_{eid}")
                        reg_count = int(ev.get("registered_count", 0))
                        new_cap = st.number_input("Capacity", min_value=max(1, reg_count), value=max(1, int(ev.get("total_seats", 1))), key=f"cap_{eid}")
                        new_desc = st.text_area("Description", value=ev.get("description", ""), key=f"desc_{eid}")

                        if st.form_submit_button("Update Event Details", type="primary"):
                            if not new_name.strip() or not new_venue.strip():
                                st.error("Event name and venue cannot be empty.")
                            else:
                                events.update_one(
                                    {"event_id": eid},
                                    {"$set": {
                                        "name": new_name.strip(),
                                        "category": new_cat,
                                        "event_date": new_dt.isoformat(),
                                        "venue": new_venue.strip(),
                                        "total_seats": int(new_cap),
                                        "description": new_desc.strip(),
                                    }},
                                )
                                registrations.update_many({"event_id": eid}, {"$set": {"event_name": new_name.strip()}})
                                st.success("Event updated successfully!")
                                st.rerun()

                    if st.button("🗑️ Delete Event and Registrations", key=f"del_btn_{eid}", type="secondary"):
                        registrations.delete_many({"event_id": eid})
                        events.delete_one({"event_id": eid})
                        st.success(f"Event and related registrations deleted.")
                        st.rerun()

    # --- PARTICIPANTS & EXPORT ---
    elif admin_page == "👥 Participants & Export":
        st.subheader("Event Participant Roster")
        if not all_events:
            st.info("No events found.")
        else:
            label_map = {f"{e['name']} ({e.get('event_date', '')})": e["event_id"] for e in all_events}
            sel_label = st.selectbox("Select Event to Inspect", list(label_map.keys()), key="admin_sel_ev")
            ev_id = label_map[sel_label]
            ev = events.find_one({"event_id": ev_id})
            people = list(registrations.find({"event_id": ev_id}).sort("student_name", ASCENDING))

            c1, c2 = st.columns([3, 1])
            c1.metric("Registered Students", len(people), help="Total students currently registered")
            if ev:
                c2.metric("Remaining Capacity", seats_left(ev))

            if people:
                data = [{
                    "Name": p.get("student_name", ""),
                    "Roll Number": p.get("roll_no", ""),
                    "Email": p.get("email", ""),
                    "Department": p.get("department", ""),
                    "Registration ID": p.get("registration_id", "")[:8],
                } for p in people]
                st.dataframe(data, use_container_width=True, hide_index=True)

                out = io.StringIO()
                writer = csv.DictWriter(out, fieldnames=["Name", "Roll Number", "Email", "Department", "Registration ID"])
                writer.writeheader()
                writer.writerows(data)
                st.download_button(
                    "📥 Export Participant List (CSV)",
                    data=out.getvalue(),
                    file_name=f"participants_{ev['name'].replace(' ', '_')}.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.info("No participants have registered for this event yet.")

    # --- MANAGE REGISTRATIONS ---
    elif admin_page == "❌ Manage Registrations":
        st.subheader("Registration Lookup & Admin Cancellation")
        filter_roll = st.text_input("Search registrations by Roll Number", key="admin_search_roll").strip().upper()
        if filter_roll:
            regs = list(registrations.find({"roll_no": filter_roll}).sort("event_name", ASCENDING))
            if not regs:
                st.info(f"No registrations found for roll number '{filter_roll}'.")
            else:
                st.write(f"Found {len(regs)} registration(s):")
                for r in regs:
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{r.get('event_name')}** — {r.get('student_name')} (`{r.get('roll_no')}`)")
                        c1.caption(f"Email: {r.get('email')} · Department: {r.get('department')} · ID: {r.get('registration_id')}")
                        if c2.button("Admin Cancel", key=f"admin_cancel_{r['registration_id']}", type="secondary"):
                            if cancel_registration(r["registration_id"]):
                                st.success("Registration revoked and seat restored.")
                                st.rerun()
                            else:
                                st.error("Failed to cancel registration.")
