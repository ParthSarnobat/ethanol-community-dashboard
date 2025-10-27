import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import json
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase

st.set_page_config(page_title="Community Ethanol Dashboard", layout="wide")
st.title("🌿 Community Ethanol Production Dashboard")

# # Load the JSON string and parse it
# firebase_creds = json.loads(st.secrets["firebase_test"]["service_account_json"])

# # Initialize Firebase Admin
# cred = credentials.Certificate(firebase_creds)
# firebase_admin.initialize_app(cred)
# db = firestore.client()

# Firebase config
config = st.secrets["firebase-test"]
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()

# -----------------------------
# Firebase connection
# -----------------------------
# Load credentials directly (no json.dumps!)
# Load the actual service account JSON string from secrets
firebase_creds_json = st.secrets["firebase-test"]["service_account_json"]
firebase_creds = json.loads(firebase_creds_json.replace("\n", "\\n"))

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -----------------------------
# Login / Signup
# -----------------------------
st.sidebar.header("🔐 Authentication")

if "user" not in st.session_state:
    # --- Login or Signup form ---
    choice = st.sidebar.selectbox("Choose Action", ["Login", "SignUp"])

    if choice == "Login":
        email = st.sidebar.text_input("Email", key="login_email")
        password = st.sidebar.text_input("Password", type="password", key="login_password")

        if st.sidebar.button("Submit", key="login_submit"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                
                # Fetch name from Firestore
                doc = db.collection("users").document(email).get()
                if doc.exists:
                    st.session_state["name"] = doc.to_dict().get("name", "Unknown")
                else:
                    st.session_state["name"] = "Unknown"

                st.session_state["user"] = email
                st.sidebar.success(f"✅ Logged in as {st.session_state['name']}")
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"❌ {e}")

    elif choice == "SignUp":
        email = st.sidebar.text_input("Email", key="signup_email")
        password = st.sidebar.text_input("Password", type="password", key="signup_password")
        name = st.sidebar.text_input("Full Name", key="signup_name")

        if st.sidebar.button("Submit", key="signup_submit"):
            try:
                user = auth.create_user_with_email_and_password(email, password)
                db.collection("users").document(email).set({
                    "email": email,
                    "name": name,
                    "created_at": firestore.SERVER_TIMESTAMP
                })
                st.sidebar.success("✅ Account created successfully! Please log in now.")
            except Exception as e:
                st.sidebar.error(f"❌ {e}")

else:
    # --- Logged in view ---
    st.sidebar.success(f"👋 Welcome, {st.session_state['name']}")
    try:
        user_data = db.collection("ethanol_data").where("user", "==", st.session_state["name"]).stream()
        user_df = pd.DataFrame([doc.to_dict() for doc in user_data])
        if not user_df.empty:
            total_ethanol = round(user_df["ethanol"].sum(), 2)
            total_waste = round(user_df["quantity"].sum(), 2)
            st.sidebar.metric("Your Total Ethanol", f"{total_ethanol} L")
            st.sidebar.metric("Your Total Waste", f"{total_waste} kg")
        else:
            st.sidebar.info("You haven't added any records yet.")
    except Exception as e:
        st.sidebar.error(f"⚠️ Error loading your data: {e}")

    logout = st.sidebar.button("🚪 Logout")
    if logout:
        for key in ["user", "name"]:
            if key in st.session_state:
                del st.session_state[key]
        st.sidebar.info("You’ve been logged out.")
        st.rerun()



st.caption("🟢 Connected to Firebase — data updates in real-time.")

collection = "ethanol_data"

# -----------------------------
# Streamlit Page Config
# -----------------------------

st.markdown("""
This app lets multiple users record ethanol production data from various waste materials 
and view combined community progress in real-time.
""")

# -----------------------------
# Sidebar - Data Entry
# -----------------------------
st.sidebar.header("➕ Add New Record")

conversion_factor = {
    "Tea Powder Waste": 0.25,
    "Matchstick Waste": 0.18,
    "Paper (Cardboard/Newspaper)": 0.22,
    "Cloth (Textile Waste)": 0.20,
    "Corn Fibres": 0.45,
    "Congress Grass": 0.30,
    "Water Hyacinth": 0.15,
    "Lantana Camara": 0.28,
    "Algae": 0.50,
    "Tamarind Waste": 0.35,
    "Peanut Shell": 0.25
}

with st.sidebar.form("data_form", clear_on_submit=True):
    waste = st.selectbox("Waste Type", list(conversion_factor.keys()))
    qty = st.number_input("Quantity (kg)", min_value=0.0, step=0.1)
    submitted = st.form_submit_button("Add Record")

    if submitted:
        if "user" not in st.session_state:
            st.sidebar.warning("⚠️ Please log in before submitting data.")
        elif waste and qty > 0:
            ethanol_generated = qty * conversion_factor[waste]
            db.collection(collection).add({
                "user": st.session_state.get("name", "Anonymous"),
                "waste_type": waste,
                "quantity": qty,
                "ethanol": ethanol_generated,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            st.sidebar.success("✅ Record added successfully!")
            st.rerun()
    else:
        st.sidebar.error("⚠️ Please fill all fields correctly.")




# -----------------------------
# Fetch Community Data
# -----------------------------
docs = db.collection(collection).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
data = [doc.to_dict() for doc in docs]

if not data:
    st.info("No community data yet. Add your first record from the sidebar!")
    st.stop()

df = pd.DataFrame(data)
df["quantity"] = df["quantity"].astype(float)
df["ethanol"] = df["ethanol"].astype(float)
if "timestamp" in df.columns:
    df["timestamp"] = df["timestamp"].fillna("").astype(str)

# -----------------------------
# Summary Metrics
# -----------------------------
st.subheader("🌍 Community Summary")

col1, col2, col3 = st.columns(3)
col1.metric("Total Waste Processed (kg)", round(df["quantity"].sum(), 2))
col2.metric("Total Ethanol Produced (litres)", round(df["ethanol"].sum(), 2))
col3.metric("Average Conversion Efficiency (%)", 
             round((df["ethanol"].sum() / df["quantity"].sum()) * 100, 2))

# -----------------------------
# Visualizations
# -----------------------------
tab1, tab2, tab3 = st.tabs(["📊 Waste vs Ethanol", "👥 By User", "📅 Data Table"])

with tab1:
    chart = px.bar(df, x="waste_type", y="ethanol", color="waste_type",
                   title="Ethanol Production by Waste Type",
                   labels={"waste_type": "Waste Type", "ethanol": "Ethanol (litres)"},
                   height=500)
    st.plotly_chart(chart, use_container_width=True)

with tab2:
    by_user = df.groupby("user")[["quantity", "ethanol"]].sum().reset_index()
    chart2 = px.bar(by_user, x="user", y="ethanol", color="user",
                    title="Top Contributors by Ethanol Produced",
                    labels={"user": "User", "ethanol": "Ethanol (litres)"})
    st.plotly_chart(chart2, use_container_width=True)

with tab3:
    st.dataframe(df[["timestamp", "user", "waste_type", "quantity", "ethanol"]], use_container_width=True)


st.success("✅ Live community dashboard connected to Firebase Firestore!")
