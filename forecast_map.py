import streamlit as st
import folium
import pandas as pd
import requests
import os
import math
import json
import re
import hashlib
import random
import smtplib
import time
import plotly.graph_objects as go
from email.mime.text import MIMEText
from streamlit_folium import st_folium
from folium.plugins import Draw
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from datetime import datetime, timedelta, timezone

# ==========================================
# 🛑 POST OFFICE CREDENTIALS (SECURED) 🛑
# ==========================================
try:
    SENDER_EMAIL = st.secrets["email"]["sender_email"]
    APP_PASSWORD = st.secrets["email"]["app_password"]
except FileNotFoundError:
    st.error("🔒 Security Alert: Missing secrets.toml file. Please contact the Lab Administrator.")
    st.stop()
except KeyError:
    st.error("🔒 Security Alert: Email credentials not properly configured in the vault.")
    st.stop()


# 1. Page Setup
st.set_page_config(page_title="Doodles' Forecast Lab", layout="wide")

# Inject Custom Font
st.html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Special+Elite&display=swap');

    p, h1, h2, h3, h4, label, .stMetricValue, .stMetricLabel, li {
        font-family: 'Special Elite', monospace !important;
    }
    
    .streamlit-expanderHeader {
        font-weight: bold;
        background-color: rgba(255,255,255,0.05);
        border-radius: 6px;
    }
    </style>
""")

# --- SECURE DATABASE & HASHING LOGIC ---
USER_DB_FILE = "doodles_users.json"

def load_users():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users_dict):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users_dict, f)

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(32).hex()
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return key.hex(), salt

def clean_username(uname):
    return re.sub(r'[^a-zA-Z0-9.\-_]', '', uname).lower()

def is_valid_password(pwd):
    if len(pwd) < 9: return False, "Password must be at least 9 characters long."
    if not any(c.isupper() for c in pwd): return False, "Password must contain at least one capital letter."
    if not any(c.isdigit() for c in pwd): return False, "Password must contain at least one number."
    if not any(not c.isalnum() for c in pwd): return False, "Password must contain at least one special character (e.g., !@?$). "
    return True, ""

def send_verification_email(to_email, code, purpose="Registration"):
    if APP_PASSWORD == "" or APP_PASSWORD == "YOUR_APP_PASSWORD_HERE":
        return False, "⚠️ Email credentials not configured in the script yet."
        
    subject = f"Doodles' Forecast Lab Verification Code: {code}"
    body = f"Hello there!\n\nYour 6-digit verification code for {purpose} is:\n\n{code}\n\nThis code will expire shortly. Do not reply to this email. Happy forecasting!\n\n- Doodles' Forecast Lab Bot 🤖"
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e:
        return False, f"Failed to send email: {e}"


# --- LOGIN & REGISTRATION PORTAL ---
if 'authenticated_user' not in st.session_state: st.session_state['authenticated_user'] = None
if 'auth_stage' not in st.session_state: st.session_state['auth_stage'] = 'start'
if 'verification_code' not in st.session_state: st.session_state['verification_code'] = None
if 'temp_user_data' not in st.session_state: st.session_state['temp_user_data'] = {}

if 'target_date' not in st.session_state: 
    st.session_state['target_date'] = datetime.now().date()

if st.session_state['authenticated_user'] is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🌪️ Doodles' Forecast Lab")
        
        if st.session_state['auth_stage'] == 'start':
            auth_mode = st.radio("Select Portal:", ["Login", "Create Account", "Forgot Password"], horizontal=True)
            
            if auth_mode == "Login":
                st.subheader("Secure System Login")
                with st.form("login_form"):
                    raw_username = st.text_input("Username:")
                    login_pass = st.text_input("Password:", type="password")
                    submit_login = st.form_submit_button("Authenticate", type="primary", use_container_width=True)
                    
                    if submit_login:
                        login_user = clean_username(raw_username)
                        current_users = load_users()
                        user_record = current_users.get(login_user)
                        
                        if user_record:
                            stored_hash = user_record["hash"]
                            stored_salt = user_record["salt"]
                            test_hash, _ = hash_password(login_pass, stored_salt)
                            
                            if test_hash == stored_hash:
                                st.session_state['temp_user_data'] = {'user': login_user}
                                st.session_state['auth_stage'] = 'tos_gateway'
                                st.rerun()
                            else: st.error("❌ Invalid Username or Password.")
                        else: st.error("❌ Invalid Username or Password.")
                        
            elif auth_mode == "Create Account":
                st.subheader("Register New Chaser")
                new_username = st.text_input("Choose a Username:")
                st.caption("Allowed: Letters, Numbers, Periods (.), Hyphens (-), Underscores (_)")
                new_email = st.text_input("Valid Email Address:")
                new_pass = st.text_input("Choose a Password:", type="password")
                st.caption("🔐 **Requirements:** Min. 9 characters, 1 uppercase, 1 number, and 1 special character (!@?$).")
                confirm_pass = st.text_input("Confirm Password:", type="password")
                
                with st.expander("📜 Read Terms of Service"):
                    st.markdown("""
                    * **1. Life Safety & Liability:** Doodles' Forecast Lab is an experimental forecasting tool, not an official government warning system. You are 100% responsible for your own safety, navigation, and decisions while storm chasing. Do not use this as a replacement for the National Weather Service.
                    * **2. Sharing & Intellectual Property:** You are encouraged to share screenshots of your forecasts! Please use the "Hide Overlays for Image" button to ensure the Doodles' Forecast Lab watermark is visible on your posts.
                    * **3. Account Conduct:** Keep it professional. Do not share your password or abuse the lab's resources. We reserve the right to ban or delete accounts for unprofessional behavior or security violations.
                    * **4. Privacy & Data:** Your password is cryptographically secured. We will never sell your personal data—mostly because the creator is genuinely not smart enough to figure out how to sell email addresses even if he wanted to.
                    * **5. Support the Lab:** Stay weather aware, and be sure to follow **Doodles' Weather Updates** on Facebook and YouTube!
                    """)
                tos_agreed = st.checkbox("I agree to the Doodles' Weather Updates Terms of Service")
                
                if st.button("Send Verification Code", type="primary", use_container_width=True):
                    clean_new_user = clean_username(new_username)
                    current_users = load_users()
                    email_exists = any(u.get('email') == new_email.lower() for u in current_users.values())
                    pwd_is_valid, pwd_msg = is_valid_password(new_pass)
                    
                    if not tos_agreed: st.warning("⚠️ You must agree to the Terms of Service to register.")
                    elif not clean_new_user: st.warning("⚠️ Please enter a valid username.")
                    elif clean_new_user in current_users: st.error("❌ That username is already taken.")
                    elif email_exists: st.error("❌ An account with that email already exists.")
                    elif "@" not in new_email: st.warning("⚠️ Please enter a valid email address.")
                    elif not pwd_is_valid: st.error(f"❌ {pwd_msg}")
                    elif new_pass != confirm_pass: st.error("❌ Passwords do not match.")
                    else:
                        with st.spinner("Dispatching verification email..."):
                            gen_code = str(random.randint(100000, 999999))
                            success, msg = send_verification_email(new_email, gen_code, "Account Registration")
                            if success:
                                st.session_state['verification_code'] = gen_code
                                st.session_state['temp_user_data'] = {'user': clean_new_user, 'pass': new_pass, 'email': new_email.lower()}
                                st.session_state['auth_stage'] = 'awaiting_reg_code'
                                st.rerun()
                            else: st.error(msg)
                            
            elif auth_mode == "Forgot Password":
                st.subheader("Account Recovery")
                st.markdown("Enter your username to receive a reset code to your registered email.")
                target_user = clean_username(st.text_input("Username:"))
                
                if st.button("Send Reset Code", type="primary", use_container_width=True):
                    current_users = load_users()
                    if target_user in current_users:
                        target_email = current_users[target_user].get('email')
                        if target_email:
                            with st.spinner("Dispatching reset code..."):
                                gen_code = str(random.randint(100000, 999999))
                                success, msg = send_verification_email(target_email, gen_code, "Password Reset")
                                if success:
                                    st.session_state['verification_code'] = gen_code
                                    st.session_state['temp_user_data'] = {'user': target_user}
                                    st.session_state['auth_stage'] = 'awaiting_reset_code'
                                    st.rerun()
                                else: st.error(msg)
                        else: st.error("❌ No email found for this legacy account. Contact Admin.")
                    else: st.error("❌ Username not found.")

        elif st.session_state['auth_stage'] == 'awaiting_reg_code':
            st.subheader("📧 Verification Waiting Room")
            st.info(f"We sent a 6-digit code to **{st.session_state['temp_user_data']['email']}**.")
            entered_code = st.text_input("Enter 6-Digit Code:", max_chars=6)
            
            if st.button("Verify & Create Account", type="primary", use_container_width=True):
                if entered_code == st.session_state['verification_code']:
                    new_hash, new_salt = hash_password(st.session_state['temp_user_data']['pass'])
                    current_users = load_users()
                    current_users[st.session_state['temp_user_data']['user']] = {
                        "hash": new_hash,
                        "salt": new_salt,
                        "email": st.session_state['temp_user_data']['email']
                    }
                    save_users(current_users)
                    st.success("✅ Verification successful! Account created. Redirecting to login...")
                    st.session_state['auth_stage'] = 'start'
                    st.session_state['verification_code'] = None
                    st.session_state['temp_user_data'] = {}
                    time.sleep(2)
                    st.rerun()
                else: st.error("❌ Incorrect code. Please try again.")
                
            if st.button("Cancel & Go Back"):
                st.session_state['auth_stage'] = 'start'
                st.rerun()

        elif st.session_state['auth_stage'] == 'awaiting_reset_code':
            st.subheader("🔐 Password Reset Waiting Room")
            st.info("Check your email for the 6-digit reset code.")
            entered_code = st.text_input("Enter 6-Digit Code:", max_chars=6)
            
            if st.button("Verify Code", type="primary", use_container_width=True):
                if entered_code == st.session_state['verification_code']:
                    st.session_state['auth_stage'] = 'resetting_password'
                    st.rerun()
                else: st.error("❌ Incorrect code. Please try again.")
                
            if st.button("Cancel & Go Back"):
                st.session_state['auth_stage'] = 'start'
                st.rerun()
                
        elif st.session_state['auth_stage'] == 'resetting_password':
            st.subheader("🔑 Enter New Password")
            new_pass = st.text_input("New Password:", type="password")
            st.caption("🔐 **Requirements:** Min. 9 characters, 1 uppercase, 1 number, and 1 special character (!@?$).")
            confirm_pass = st.text_input("Confirm New Password:", type="password")
            
            if st.button("Update Password", type="primary", use_container_width=True):
                pwd_is_valid, pwd_msg = is_valid_password(new_pass)
                if not pwd_is_valid: st.error(f"❌ {pwd_msg}")
                elif new_pass != confirm_pass: st.error("❌ Passwords do not match.")
                else:
                    target_user = st.session_state['temp_user_data']['user']
                    current_users = load_users()
                    new_hash, new_salt = hash_password(new_pass)
                    current_users[target_user]["hash"] = new_hash
                    current_users[target_user]["salt"] = new_salt
                    save_users(current_users)
                    st.success("✅ Password successfully updated! Redirecting to login...")
                    st.session_state['auth_stage'] = 'start'
                    st.session_state['verification_code'] = None
                    st.session_state['temp_user_data'] = {}
                    time.sleep(2)
                    st.rerun()

        elif st.session_state['auth_stage'] == 'tos_gateway':
            st.subheader("📜 Terms of Service")
            st.markdown(f"Welcome back, **{st.session_state['temp_user_data']['user']}**. Please acknowledge the rules before entering the lab.")
            
            with st.form("tos_form"):
                st.info("""
                * **1. Life Safety & Liability:** Doodles' Forecast Lab is an experimental forecasting tool, not an official government warning system. You are 100% responsible for your own safety, navigation, and decisions while storm chasing. Do not use this as a replacement for the National Weather Service.
                * **2. Sharing & Intellectual Property:** You are encouraged to share screenshots of your forecasts! Please use the "Hide Overlays for Image" button to ensure the Doodles' Forecast Lab watermark is visible on your posts.
                * **3. Account Conduct:** Keep it professional. Do not share your password or abuse the lab's resources. We reserve the right to ban or delete accounts for unprofessional behavior or security violations.
                * **4. Privacy & Data:** Your password is cryptographically secured. We will never sell your personal data—mostly because the creator is genuinely not smart enough to figure out how to sell email addresses even if he wanted to.
                * **5. Support the Lab:** Stay weather aware, and be sure to follow **Doodles' Weather Updates** on Facebook and YouTube!
                """)
                tos_agreed = st.checkbox("I agree to the Doodles' Weather Updates Terms of Service")
                
                submitted_tos = st.form_submit_button("Enter Forecast Lab", type="primary", use_container_width=True)
                
                if submitted_tos:
                    if tos_agreed:
                        st.session_state['authenticated_user'] = st.session_state['temp_user_data']['user']
                        st.session_state['auth_stage'] = 'start'
                        st.session_state['temp_user_data'] = {}
                        st.rerun()
                    else:
                        st.warning("⚠️ You must agree to the Terms of Service to access the lab.")
            
            if st.button("Cancel & Go Back"):
                st.session_state['auth_stage'] = 'start'
                st.session_state['temp_user_data'] = {}
                st.rerun()
                    
    st.stop()


def render_help_instructions():
    st.markdown("---")
    st.subheader("📖 Dashboard Help & Instructions")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        **1. Create a Forecast:**
        * Select Date, Time, Region, and Hazard on the left.
        * Draw your polygon(s) on the map using the tool.
        * Click **✅ Lock Active Layer**.
        * Click **📥 Download Forecast** to save the JSON.
        """)
    with c2:
        st.markdown("""
        **2. Verify a Forecast:**
        * Go to the Verification Map tab.
        * Upload your saved JSON file.
        * Review your Calibration and CSI Scores.
        * Click **Save Verified Outlook** to log it.
        """)
    with c3:
        st.markdown("""
        **3. Take a Map Screenshot:**
        * Click **👁️ Hide Overlays for Image** (on the right).
        * Use your computer's native tool:
          * **Windows:** `Win + Shift + S`
          * **Mac:** `Cmd + Shift + 4`
        * Click **👁️ Display All Overlays** to bring tools back.
        """)


user_history_file = f"history_{st.session_state['authenticated_user']}.csv"

st.sidebar.markdown(f"👤 Logged in as: **{st.session_state['authenticated_user'].capitalize()}**")
if st.sidebar.button("Logout", key="logout_btn"):
    st.session_state['authenticated_user'] = None
    st.session_state['auth_stage'] = 'start'
    st.rerun()
st.sidebar.markdown("---")

CAT_COLORS = {
    "TSTM (Light Green)": {"hex": "#C1E8A4", "prob": 5}, 
    "MRGL (Dark Green)": {"hex": "#008B00", "prob": 10},
    "SLGT (Yellow)": {"hex": "#FFFF00", "prob": 15}, 
    "ENH (Orange)": {"hex": "#FF8C00", "prob": 30},
    "MDT (Red)": {"hex": "#FF0000", "prob": 45}, 
    "HIGH (Magenta)": {"hex": "#FF00FF", "prob": 60}
}
TOR_COLORS = {
    "2% (Dark Green)": {"hex": "#008B00", "prob": 2}, "5% (Brown)": {"hex": "#8B4726", "prob": 5},
    "10% (Yellow)": {"hex": "#FFFF00", "prob": 10}, "15% (Red)": {"hex": "#FF0000", "prob": 15},
    "30% (Pink)": {"hex": "#FF00FF", "prob": 30}, "45% (Purple)": {"hex": "#912CEE", "prob": 45},
    "60% (Blue)": {"hex": "#0000CD", "prob": 60}
}
WIND_HAIL_COLORS = {
    "5% (Brown)": {"hex": "#8B4726", "prob": 5}, "15% (Yellow)": {"hex": "#FFFF00", "prob": 15},
    "30% (Red)": {"hex": "#FF0000", "prob": 30}, "45% (Pink)": {"hex": "#FF00FF", "prob": 45},
    "60% (Purple)": {"hex": "#912CEE", "prob": 60}
}

NWS_OFFICES = [
    "ALL", "ABQ (Albuquerque)", "ABR (Aberdeen)", "AFC (Anchorage)", "AFG (Fairbanks)", 
    "AJK (Juneau)", "AKQ (Wakefield)", "ALY (Albany)", "AMA (Amarillo)", "APX (Gaylord)", 
    "ARX (La Crosse)", "BGM (Binghamton)", "BIS (Bismarck)", "BMX (Birmingham)", "BOI (Boise)", 
    "BOU (Denver/Boulder)", "BOX (Boston/Norton)", "BRO (Brownsville)", "BTV (Burlington)", "BYZ (Billings)", 
    "CAE (Columbia)", "CAR (Caribou)", "CHS (Charleston, SC)", "CLE (Cleveland)", "CRP (Corpus Christi)", 
    "CYS (Cheyenne)", "DDC (Dodge City)", "DLH (Duluth)", "DMX (Des Moines)", "DTX (Detroit/Pontiac)", 
    "DVN (Quad Cities)", "EAX (Kansas City)", "EKA (Eureka)", "EPZ (El Paso)", "EWX (Austin/San Antonio)", 
    "EYW (Key West)", "FFC (Peachtree City/Atlanta)", "FGF (Grand Forks)", "FGZ (Flagstaff)", "FSD (Sioux Falls)", 
    "FWD (Dallas/Fort Worth)", "GGW (Glasgow)", "GJT (Grand Junction)", "GLD (Goodland)", "GRB (Green Bay)", 
    "GRR (Grand Rapids)", "GSP (Greenville/Spartanburg)", "GYX (Gray/Portland)", "HNX (Hanford)", "HOU (Houston/Galveston)", 
    "HUN (Huntsville)", "ICT (Wichita)", "ILM (Wilmington, NC)", "ILN (Wilmington, OH)", "ILX (Lincoln)", 
    "IND (Indianapolis)", "IWX (Northern Indiana)", "JAN (Jackson, MS)", "JAX (Jacksonville)", "JKL (Jackson, KY)", 
    "LBF (North Platte)", "LCH (Lake Charles)", "LIX (New Orleans/Baton Rouge)", "LKN (Elko)", "LMK (Louisville)", 
    "LOT (Chicago)", "LSX (St. Louis)", "LUB (Lubbock)", "LWX (Sterling/DC)", "LZK (Little Rock)", 
    "MAF (Midland/Odessa)", "MEG (Memphis)", "MFL (Miami)", "MFR (Medford)", "MHX (Newport/Morehead City)", 
    "MKX (Milwaukee/Sullivan)", "MLB (Melbourne)", "MOB (Mobile)", "MPX (Minneapolis)", "MQT (Marquette)", 
    "MRX (Morristown/Knoxville)", "MSO (Missoula)", "MTR (San Francisco/Monterey)", "OAX (Omaha/Valley)", "OHX (Nashville)", 
    "OKX (New York/Upton)", "OTX (Spokane)", "OUN (Norman/OKC)", "PAH (Paducah)", "PBZ (Pittsburgh)", 
    "PDT (Pendleton)", "PHI (Mount Holly/Philadelphia)", "PIH (Pocatello/Idaho Falls)", "PQR (Portland, OR)", "PSR (Phoenix)", 
    "PUB (Pueblo)", "RAH (Raleigh)", "REV (Reno)", "RIW (Riverton)", "RLX (Charleston, WV)", "RNK (Blacksburg)", 
    "SEW (Seattle)", "SGF (Springfield, MO)", "SGX (San Diego)", "SHV (Shreveport)", "SJT (San Angelo)", 
    "SJU (San Juan)", "SLC (Salt Lake City)", "STO (Sacramento)", "TAE (Tallahassee)", "TBW (Tampa Bay)", 
    "TFX (Great Falls)", "TOP (Topeka)", "TSA (Tulsa)", "TWC (Tucson)", "UNR (Rapid City)", "VEF (Las Vegas)"
]

if 'locked_forecasts' not in st.session_state: st.session_state['locked_forecasts'] = []
if 'map_key' not in st.session_state: st.session_state['map_key'] = 0
if 'verify_forecasts' not in st.session_state: st.session_state['verify_forecasts'] = []
if 'hide_overlays' not in st.session_state: st.session_state['hide_overlays'] = False
if 'issue_time' not in st.session_state: st.session_state['issue_time'] = pd.Timestamp.now('US/Central').strftime('%H:%M')


tab_active, tab_verify, tab_spc, tab_analytics, tab_about = st.tabs([
    "🗺️ Active Forecast Map", 
    "⚖️ Forecast Verification Map", 
    "🗺️ SPC Reference Map",
    "📈 Forecast Analytics",
    "ℹ️ About & Docs"
])

with st.sidebar.expander("📅 Step 1 & 2: Time & Region", expanded=True):
    selected_date = st.date_input("Forecast Valid Date:", value=st.session_state['target_date'])
    d_str = selected_date.strftime("%Y-%m-%d")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        issued_date = st.date_input("Issued Date:", selected_date)
    with col_t2:
        issued_time_raw = st.text_input("Issued Time (HH:MM):", value=st.session_state['issue_time'])
        safe_time_str = "".join([char for char in issued_time_raw if char.isdigit() or char == ':'])
        
    target_office = st.selectbox("Filter by NWS Office:", NWS_OFFICES)
    office_id = target_office.split(" ")[0]

with st.sidebar.expander("🖍️ Step 3: Active Shape Attributes", expanded=True):
    st.error("⚠️ **CRITICAL WORKFLOW:** Click 'Lock Layer' on the map BEFORE changing the Risk Level!")
    forecast_mode = st.radio("Forecast Mode:", ["Categorical (All Severe)", "Probabilistic (Targeted)"])
    target_hazard = "ALL"

    if forecast_mode == "Categorical (All Severe)":
        active_bank = CAT_COLORS
    else:
        target_hazard = st.selectbox("Target Hazard:", ["TORNADO", "WIND", "HAIL"])
        active_bank = TOR_COLORS if target_hazard == "TORNADO" else WIND_HAIL_COLORS

    selected_label = st.selectbox("Risk Level / Color:", list(active_bank.keys()))
    current_color = active_bank[selected_label]["hex"]
    default_prob = active_bank[selected_label]["prob"]

    forecast_prob = st.number_input("Probability (%)", min_value=0, max_value=100, value=default_prob, step=1)
    
    st.markdown("---")
    map_theme = st.radio("Basemap Theme:", ["Dark Mode", "Light Mode"])

display_hazard_title = "CATEGORICAL" if forecast_mode == "Categorical (All Severe)" else target_hazard
valid_date_formatted = selected_date.strftime("%m/%d/%Y")
custom_issue_str = f"ISSUED: {safe_time_str} CT {issued_date.strftime('%m/%d/%Y')}"
base_tileset = "cartodbdark_matter" if map_theme == "Dark Mode" else "cartodbpositron"

WFO_COORDS = {"AKQ": [36.98, -77.00], "OUN": [35.23, -97.46]} 
map_center = WFO_COORDS.get(office_id, [39.82, -98.57])
zoom = 7 if office_id != "ALL" else 4

@st.cache_data(ttl=900, show_spinner="Fetching Live LSR Data...")
def get_lsr_data(selected_date_str):
    base_dt = datetime.strptime(selected_date_str, "%Y-%m-%d")
    next_day = base_dt + timedelta(days=1)
    start_str = selected_date_str + "T12:00Z"
    end_str = next_day.strftime("%Y-%m-%d") + "T11:59Z"
    url = f"https://mesonet.agron.iastate.edu/cgi-bin/request/gis/lsr.py?sts={start_str}&ets={end_str}&wfo=ALL&fmt=csv"
    try: 
        df = pd.read_csv(url, on_bad_lines='skip', engine='python')
        if 'valid' in df.columns: df['TIME'] = pd.to_datetime(df['valid'], errors='coerce', utc=True)
        else: df['TIME'] = pd.NaT
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner="Fetching NWS DAT Data...")
def get_dat_data(start_epoch, end_time_param, end_epoch):
    points_list = []
    tracks_list = []
    def fetch_layer(layer_id):
        features = []
        offset = 0
        while True:
            dat_url = f"https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/{layer_id}/query?where=1=1&time={start_epoch},{end_time_param}&outFields=*&resultOffset={offset}&f=geojson"
            try:
                res = requests.get(dat_url, timeout=10).json()
                if 'features' in res and len(res['features']) > 0:
                    features.extend([f for f in res['features'] if not f.get('properties', {}).get('stormdate') or start_epoch <= f['properties']['stormdate'] <= end_epoch])
                    if res.get('exceededTransferLimit'): offset += len(res['features'])
                    else: break
                else: break
            except: break
        return features
        
    for f in fetch_layer(0):
        geom = f.get('geometry')
        if geom and geom['type'] == 'Point':
            props = f.get('properties', {})
            storm_ms = props.get('stormdate', props.get('STORMDATE'))
            dt = pd.to_datetime(storm_ms, unit='ms', utc=True) if storm_ms else pd.NaT
            points_list.append({'LAT': geom['coordinates'][1], 'LON': geom['coordinates'][0], 'TYPETEXT': props.get('event_type', 'UNKNOWN'), 'MAG': props.get('windspeed', 0), 'WFO': props.get('wfo', ''), 'TIME': dt})
    tracks_list = fetch_layer(1) + fetch_layer(2)
    return pd.DataFrame(points_list), tracks_list

@st.cache_data(ttl=900, show_spinner="Fetching SPC GeoJSON Database...")
def get_spc_geojson(date_str, hazard_code):
    d_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    delta_days = (d_obj - today).days
    day_num = delta_days + 1
    urls_to_try = []
    if day_num == 1:
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day1otlk_{hazard_code}.nolyr.geojson")
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day1otlk_{hazard_code}.lyr.geojson")
    elif day_num == 2:
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day2otlk_{hazard_code}.nolyr.geojson")
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day2otlk_{hazard_code}.lyr.geojson")
    elif day_num == 3:
        hc = "cat" if hazard_code == "cat" else "prob"
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day3otlk_{hc}.nolyr.geojson")
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day3otlk_{hc}.lyr.geojson")
    elif 4 <= day_num <= 8:
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day48otlk_prob.nolyr.geojson")
        urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/day48otlk_prob.lyr.geojson")
    elif day_num < 1:
        times = ['2000', '1630', '1300', '1200', '0100']
        yyyy = d_obj.strftime("%Y")
        yyyymmdd = d_obj.strftime("%Y%m%d")
        for t in times:
            urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/archive/{yyyy}/day1otlk_{yyyymmdd}_{t}_{hazard_code}.nolyr.geojson")
            urls_to_try.append(f"https://www.spc.noaa.gov/products/outlook/archive/{yyyy}/day1otlk_{yyyymmdd}_{t}_{hazard_code}.lyr.geojson")
    for url in urls_to_try:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200: 
                return r.json()
        except: 
            continue
    return None

def evaluate_outlook(hazard_layers, f_df, c_tracks, t_hazard, src_type):
    obs_shapes = []
    for _, r in f_df.iterrows():
        is_target = True if t_hazard == "ALL" or t_hazard in str(r['TYPETEXT']).upper() else False
        if is_target:
            pt = Point(r['LON'], r['LAT'])
            obs_shapes.append(pt.buffer(0.36))
            
    if src_type == "Hybrid (Live LSRs + Official DAT Tracks)" and c_tracks:
        for track in c_tracks:
            props = track.get('properties', {})
            event_type = str(props.get('event_type', props.get('EVENT_TYPE', 'TORNADO'))).upper()
            is_target = True if t_hazard == "ALL" or t_hazard in event_type else False
            if is_target:
                t_geom = shape(track['geometry'])
                obs_shapes.append(t_geom.buffer(0.36))

    observed_polygon = unary_union(obs_shapes) if obs_shapes else None

    results = {}
    for layer in hazard_layers:
        p = layer['prob']
        fcst_shapes = [shape(feat['geometry']) for feat in layer['geometry']['features']]
        fcst_polygon = unary_union(fcst_shapes) if fcst_shapes else None
        
        if fcst_polygon and observed_polygon:
            intersection = fcst_polygon.intersection(observed_polygon)
            a = intersection.area 
            b = fcst_polygon.area - a 
            c = observed_polygon.area - a 
            
            pod = (a / (a + c)) * 100 if (a + c) > 0 else 0.0
            far = (b / (a + b)) * 100 if (a + b) > 0 else 0.0
            csi = (a / (a + b + c)) * 100 if (a + b + c) > 0 else 0.0
            obs_coverage = (a / fcst_polygon.area) * 100 if fcst_polygon.area > 0 else 0.0
            
        elif fcst_polygon and not observed_polygon:
            pod, far, csi, obs_coverage = 0.0, 100.0, 0.0, 0.0
        else:
            pod, far, csi, obs_coverage = 0.0, 0.0, 0.0, 0.0
            
        if p > 0:
            if obs_coverage == 0.0:
                cal_score = 0.0
            elif obs_coverage <= p:
                cal_score = (obs_coverage / p) * 100.0
            else:
                cal_score = (p / obs_coverage) * 100.0
        else:
            cal_score = 0.0
            
        results[p] = {
            'csi': csi, 'pod': pod, 'far': far, 'obs_coverage': obs_coverage, 'cal_score': cal_score
        }
    return results, observed_polygon

def apply_overlay_hide(m):
    # 1. PERMANENT WATERMARK (Always added, never hidden)
    watermark_html = '''
        <div style="position: absolute; bottom: 30px; right: 30px; z-index: 9999;
        background: rgba(0, 32, 78, 0.7); backdrop-filter: blur(5px); 
        padding: 10px 20px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.4);
        color: white; font-family: 'Special Elite', monospace !important;
        font-size: 18px; font-weight: bold; pointer-events: none; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
        🌩️ Doodles' Forecast Lab
        </div>
    '''
    m.get_root().html.add_child(folium.Element(watermark_html))
    
    # 2. TOGGLE UI CONTROLS (Only hides zoom/draw buttons when toggled)
    if st.session_state.get('hide_overlays', False):
        hide_css = """<style>.leaflet-control-container { display: none !important; }</style>"""
        m.get_root().html.add_child(folium.Element(hide_css))

def build_map_legend(hazard_mode, active_bank_dict, verification_dots=""):
    hazard_upper = str(hazard_mode).upper()
    if "CATEGORICAL" in hazard_upper or "ALL" in hazard_upper or "CATEGORICAL (ALL SEVERE)" in hazard_upper:
        legend_title = "Categorical Risk"
    elif "TORNADO" in hazard_upper:
        legend_title = "TORNADO Probabilities"
    else:
        legend_title = "WIND/HAIL Probabilities"
    
    risk_rows = ""
    for label, data in active_bank_dict.items():
        clean_label = label.split(" (")[0]
        risk_rows += f'<div style="margin-bottom: 2px;"><i style="background: {data["hex"]}; width: 14px; height: 14px; display: inline-block; border-radius: 3px; margin-right: 8px; border: 1px solid rgba(255,255,255,0.5);"></i>{clean_label}</div>'

    v_dots_html = f'''
        <div style="font-family: 'Special Elite', monospace !important; font-weight: bold; margin-top: 10px; margin-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px;">Verification Data</div>
        <div style="font-family: 'Special Elite', monospace !important;">{verification_dots}</div>
    ''' if verification_dots else ""

    legend_html = f'''
        <div style="position: absolute; bottom: 30px; left: 30px; width: auto; min-width: 160px; 
        background: rgba(0, 32, 78, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.3); z-index:1000; 
        font-size:14px; padding: 15px; border-radius: 12px; color: white;">
        <div style="font-family: 'Special Elite', monospace !important; font-weight: bold; margin-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px;">{legend_title}</div>
        <div style="font-family: 'Special Elite', monospace !important;">{risk_rows}</div>
        {v_dots_html}
        </div>
    '''
    return legend_html


with tab_active:
    st.subheader("🖍️ Forecast Creation Canvas")
    
    # --- THE FIX: BUMPER COLUMNS TO CONSTRAIN THE WIDTH ---
    col_spacer_l, col_map, col_buttons, col_spacer_r = st.columns([1, 5, 1.5, 1])

    with col_map:
        m_create = folium.Map(location=map_center, zoom_start=zoom, tiles=None)
        folium.TileLayer(base_tileset, cross_origin=True, crossOrigin=True).add_to(m_create)

        title_html = f'''
            <div style="position: absolute; top: 15px; left: 50%; transform: translateX(-50%);
            background: rgba(0, 32, 78, 0.85); backdrop-filter: blur(5px); border: 2px solid white; color: white;
            padding: 8px 20px; border-radius: 8px; font-family: 'Special Elite', monospace !important;
            font-size: 18px; font-weight: bold; text-align: center; z-index: 1000; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
            {display_hazard_title} FORECAST VALID {valid_date_formatted}
            <br><span style='font-size: 13px; font-weight: normal; color: #cccccc;'>{custom_issue_str}</span>
            <br><span style='font-size: 14px; color: #ffcc00; font-weight: bold;'>⚠️ EXPERIMENTAL AND NOT SPC ⚠️</span>
            </div>
        '''
        m_create.get_root().html.add_child(folium.Element(title_html))

        legend_html = build_map_legend(display_hazard_title, active_bank)
        m_create.get_root().html.add_child(folium.Element(legend_html))

        for lf in st.session_state['locked_forecasts']:
            folium.GeoJson(lf['geometry'], style_function=lambda x, c=lf['color']: {'fillColor': c, 'color': c, 'fillOpacity': 0.15, 'weight': 4}).add_to(m_create)

        Draw(export=False, draw_options={'polyline': False, 'rectangle': False, 'circle': False, 'marker': False, 'circlemarker': False, 'polygon': {'shapeOptions': {'color': current_color, 'weight': 4, 'fillOpacity': 0.15, 'fillColor': current_color}}}).add_to(m_create)

        apply_overlay_hide(m_create)

        map_signature = f"create_map_{st.session_state['map_key']}_{display_hazard_title}_{valid_date_formatted}_{map_theme}_{custom_issue_str}_{st.session_state['hide_overlays']}"
        
        # --- THE FIX: USE CONTAINER WIDTH RE-ENABLED INSIDE BUMPERS ---
        output_create = st_folium(m_create, use_container_width=True, height=700, key=map_signature)

    with col_buttons:
        if st.button("✅ Lock Active Layer", type="primary", use_container_width=True):
            active_drawings = output_create.get("all_drawings", []) if output_create else []
            if active_drawings:
                combined_geojson = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": d['geometry'], "properties": {}} for d in active_drawings]}
                st.session_state['locked_forecasts'].append({'geometry': combined_geojson, 'hazard': target_hazard, 'prob': forecast_prob, 'color': current_color})
                st.session_state['map_key'] += 1
                st.session_state['issue_time'] = pd.Timestamp.now('US/Central').strftime('%H:%M')
                st.rerun()
            else: st.warning("Draw a shape first!")
        
        if st.button("🗑️ Clear Creation Canvas", use_container_width=True):
            st.session_state['locked_forecasts'] = []
            st.session_state['map_key'] += 1
            st.rerun()
        
        if st.session_state['locked_forecasts']:
            forecast_json = json.dumps(st.session_state['locked_forecasts'])
            st.download_button(label="📥 Download Forecast (.json)", data=forecast_json, file_name=f"Forecast_{display_hazard_title}_{d_str}.json", mime="application/json", use_container_width=True)
        else: 
            st.button("📥 Download Forecast (.json)", disabled=True, use_container_width=True)
            
        st.markdown("---")
        btn_text = "👁️ Display All Overlays" if st.session_state['hide_overlays'] else "👁️ Hide Overlays for Image"
        if st.button(btn_text, use_container_width=True, key="toggle_t1"):
            st.session_state['hide_overlays'] = not st.session_state['hide_overlays']
            st.rerun()

    render_help_instructions()

with tab_verify:
    st.subheader("⚖️ HVS Verification & Analytics Engine")

    col_v1, col_v2 = st.columns([1, 2])
    with col_v1:
        st.markdown("**1. Configure Verification Data**")
        source_type = st.radio("Source Priority:", ["Hybrid (Live LSRs + Official DAT Tracks)", "Live LSRs Only"], key="v_src")
        event_types = st.multiselect("Active Hazards:", ["TORNADO", "WIND", "HAIL"], default=["TORNADO", "WIND", "HAIL"], key="v_haz")
        
        st.info("ℹ️ Using NWS Area-Based Verification. The engine automatically draws a 25-mile footprint around all valid reports.")
        min_hail = st.slider("Min Hail (In):", 1.00, 4.00, 1.00, 0.25, key="v_hail") if "HAIL" in event_types else 1.00
        min_wind = st.slider("Min Wind (Kts):", 50, 100, 50, 5, key="v_wind") if "WIND" in event_types else 50
        
    with col_v2:
        st.markdown("**2. Load the Forecast JSON**")
        st.warning("⚠️ **Important:** To verify historical forecasts, you MUST manually change the **Forecast Valid Date** in the left sidebar to match the date of your forecast before uploading.")
        uploaded_file = st.file_uploader("Upload your saved JSON here to overlay the verification data.", type="json")
        if uploaded_file is not None:
            if st.button("Load JSON onto Verification Map", type="primary"):
                try:
                    loaded_data = json.load(uploaded_file)
                    st.session_state['verify_forecasts'] = loaded_data
                    st.session_state['map_key'] += 1
                    st.rerun()
                except Exception as e: 
                    st.error(f"Failed to load: {e}")
        
        if st.button("🗑️ Clear Verification Engine", type="secondary"):
            st.session_state['verify_forecasts'] = []
            st.session_state['map_key'] += 1
            st.rerun()

    if st.session_state['verify_forecasts']:
        st.markdown("---")
        v_hazard = st.session_state['verify_forecasts'][0]['hazard']
        
        reports_df = get_lsr_data(d_str)
        confirmed_tracks = []
        if source_type == "Hybrid (Live LSRs + Official DAT Tracks)":
            start_dt = datetime(selected_date.year, selected_date.month, selected_date.day, 12, 0, 0, tzinfo=timezone.utc)
            s_ep = int(start_dt.timestamp() * 1000)
            _, confirmed_tracks = get_dat_data(s_ep, s_ep + 604800000, s_ep + 86400000)
            
        if not reports_df.empty:
            if office_id != "ALL": reports_df = reports_df[reports_df['WFO'].str.contains(office_id, case=False, na=False)]
            mask = reports_df['TYPETEXT'].str.contains('|'.join(event_types), case=False, na=False)
            df = reports_df[mask].copy()
            if source_type == "Hybrid (Live LSRs + Official DAT Tracks)" and len(confirmed_tracks) > 0:
                df = df[~df['TYPETEXT'].str.contains('TORNADO', case=False, na=False)]
            
            def filter_mag(row):
                rtype = str(row['TYPETEXT']).upper()
                mag = row['MAG'] if pd.notnull(row['MAG']) else 0
                if "TORNADO" in rtype: return True
                if "HAIL" in rtype: return mag >= min_hail
                if "WIND" in rtype: return mag >= min_wind
                return False
            filtered_df = df[df.apply(filter_mag, axis=1)]
        else: 
            filtered_df = pd.DataFrame()

        results, observed_footprint = evaluate_outlook(st.session_state['verify_forecasts'], filtered_df, confirmed_tracks, v_hazard, source_type)

        num_tiers = len(results)
        if num_tiers > 0:
            avg_csi = sum(s['csi'] for s in results.values()) / num_tiers
            avg_pod = sum(s['pod'] for s in results.values()) / num_tiers
            avg_far = sum(s['far'] for s in results.values()) / num_tiers
            avg_cal = sum(s['cal_score'] for s in results.values()) / num_tiers
        else:
            avg_csi, avg_pod, avg_far, avg_cal = 0, 0, 0, 0

        # --- THE FIX: BUMPER COLUMNS TO CONSTRAIN THE WIDTH ---
        col_spacer_l_v, col_map_v, col_right_v, col_spacer_r_v = st.columns([1, 5, 1.5, 1])

        with col_map_v:
            m_verify = folium.Map(location=map_center, zoom_start=zoom, tiles=None)
            folium.TileLayer(base_tileset, cross_origin=True, crossOrigin=True).add_to(m_verify)

            title_html_v = f'''
                <div style="position: absolute; top: 15px; left: 50%; transform: translateX(-50%); 
                background: rgba(0, 32, 78, 0.85); border: 2px solid white; color: white; 
                padding: 8px 20px; border-radius: 8px; font-family: 'Special Elite', monospace !important; 
                font-size: 18px; font-weight: bold; text-align: center; z-index: 1000; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
                VERIFYING {v_hazard} FORECAST VALID {valid_date_formatted}
                <br><span style='font-size: 13px; font-weight: normal; color: #cccccc;'>{custom_issue_str}</span>
                <br><span style='font-size: 14px; color: #ffcc00; font-weight: bold;'>⚠️ EXPERIMENTAL AND NOT SPC ⚠️</span>
                </div>
            '''
            m_verify.get_root().html.add_child(folium.Element(title_html_v))

            verification_dots = ""
            if "TORNADO" in event_types: verification_dots += '<div style="margin-bottom: 2px;"><i style="background: red; width: 10px; height: 10px; display: inline-block; border-radius: 50%; margin-right: 8px; margin-left: 2px;"></i>Tornado</div>'
            if "WIND" in event_types: verification_dots += '<div style="margin-bottom: 2px;"><i style="background: blue; width: 10px; height: 10px; display: inline-block; border-radius: 50%; margin-right: 8px; margin-left: 2px;"></i>Wind</div>'
            if "HAIL" in event_types: verification_dots += '<div><i style="background: green; width: 10px; height: 10px; display: inline-block; border-radius: 50%; margin-right: 8px; margin-left: 2px;"></i>Hail</div>'
            active_bank_v = CAT_COLORS if v_hazard == "ALL" else TOR_COLORS if v_hazard == "TORNADO" else WIND_HAIL_COLORS
            
            legend_html_v = build_map_legend(v_hazard, active_bank_v, verification_dots)
            m_verify.get_root().html.add_child(folium.Element(legend_html_v))

            if num_tiers > 0:
                scoreboard_html_v = f'''
                    <div style="position: absolute; top: 15px; right: 15px; 
                    background: rgba(0, 32, 78, 0.85); border: 2px solid white; color: white; 
                    padding: 10px 20px; border-radius: 8px; font-family: 'Special Elite', monospace !important; 
                    text-align: center; z-index: 1000; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
                    <div style="font-size: 16px; font-weight: bold; margin-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 5px;">Verification Scoreboard</div>
                    
                    <div style="display: flex; justify-content: space-between; gap: 20px; margin-top: 8px;">
                        <div>
                            <div style="font-size: 11px; font-weight: normal; color: #cccccc; margin-bottom: 2px;">CALIBRATION</div>
                            <div style="font-size: 24px; font-weight: bold; color: #C1E8A4;">{avg_cal:.2f}%</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; font-weight: normal; color: #cccccc; margin-bottom: 2px;">NWS CSI</div>
                            <div style="font-size: 24px; font-weight: bold;">{avg_csi:.2f}%</div>
                        </div>
                    </div>
                    </div>
                '''
                m_verify.get_root().html.add_child(folium.Element(scoreboard_html_v))
            
            for lf in st.session_state['verify_forecasts']:
                folium.GeoJson(lf['geometry'], style_function=lambda x, c=lf['color']: {'fillColor': c, 'color': c, 'fillOpacity': 0.15, 'weight': 4}).add_to(m_verify)
            
            if observed_footprint and not observed_footprint.is_empty:
                folium.GeoJson(
                    observed_footprint,
                    style_function=lambda x: {'fillColor': '#ffffff', 'color': '#ffffff', 'fillOpacity': 0.2, 'weight': 1, 'dashArray': '4, 4'}
                ).add_to(m_verify)
                
            if confirmed_tracks:
                EF_COLORS = {"EFU": "gray", "EF0": "cyan", "EF1": "green", "EF2": "yellow", "EF3": "orange", "EF4": "red", "EF5": "magenta"}
                folium.GeoJson(
                    {'type': 'FeatureCollection', 'features': confirmed_tracks}, 
                    style_function=lambda x: {'color': EF_COLORS.get(x['properties'].get('efscale', 'EFU'), 'red'), 'weight': 6, 'opacity': 1.0}, 
                    tooltip=folium.GeoJsonTooltip(fields=['efscale', 'width', 'length'])
                ).add_to(m_verify)
                
            if not filtered_df.empty:
                for _, row in filtered_df.iterrows():
                    rtype = str(row['TYPETEXT']).upper()
                    color = "red" if "TORNADO" in rtype else "blue" if "WIND" in rtype else "green"
                    tt_html = f"<div style=\"font-family: 'Special Elite', monospace; padding: 2px;\"><b>{rtype}</b></div>"
                    folium.CircleMarker(
                        location=[row['LAT'], row['LON']], 
                        radius=5, 
                        color="white", 
                        weight=1, 
                        fill=True, 
                        fill_color=color, 
                        fill_opacity=0.9, 
                        tooltip=folium.Tooltip(tt_html)
                    ).add_to(m_verify)

            apply_overlay_hide(m_verify)
            # --- THE FIX: USE CONTAINER WIDTH RE-ENABLED INSIDE BUMPERS ---
            st_folium(m_verify, use_container_width=True, height=700, key=f"verify_map_{st.session_state['map_key']}_{valid_date_formatted}_{custom_issue_str}_{st.session_state['hide_overlays']}")

        with col_right_v:
            if st.button("💾 Save Verified Outlook", type="primary", use_container_width=True):
                rows_to_save = []
                for p, stats in results.items():
                    rows_to_save.append({
                        'Date': d_str,
                        'Hazard': v_hazard,
                        'Forecast_Prob': p,
                        'Obs_Coverage': stats['obs_coverage'],
                        'CSI': stats['csi'],
                        'POD': stats['pod'],
                        'FAR': stats['far'],
                        'Cal_Score': stats['cal_score']
                    })
                
                pd.DataFrame(rows_to_save).to_csv(user_history_file, mode='a', header=not os.path.exists(user_history_file), index=False)
                st.success("Outlook Successfully Archived!")
            
            st.markdown("### Tier Breakdown")
            if num_tiers > 0:
                for p, stats in sorted(results.items(), reverse=True):
                    st.markdown(f"**Tier {p}%:**")
                    st.markdown(f"🛡️ **{stats['cal_score']:.2f}%** Calibrated")
                    st.caption(f"*(CSI: {stats['csi']:.0f}% | POD: {stats['pod']:.0f}% | FAR: {stats['far']:.0f}%)*")
                    st.markdown("---")
                    
            btn_text_v = "👁️ Display All Overlays" if st.session_state['hide_overlays'] else "👁️ Hide Overlays for Image"
            if st.button(btn_text_v, use_container_width=True, key="toggle_t2"):
                st.session_state['hide_overlays'] = not st.session_state['hide_overlays']
                st.rerun()
                
        render_help_instructions()

with tab_spc:
    st.subheader("🗺️ Official SPC Reference Map")
    st.markdown("Pulling official spatial polygons directly from the Storm Prediction Center database.")
    
    st.info("⚠️ **Disclaimer:** This lab supports viewing official SPC forecasts for **Day 1 through Day 3 only**. Day 4-8 outlooks are not available in this module.")
    
    delta_days = (datetime.strptime(d_str, "%Y-%m-%d").date() - datetime.now().date()).days
    spc_day_num = delta_days + 1

    spc_view_hazard = st.radio("Select SPC Outlook to View:", ["Categorical", "Tornado", "Wind", "Hail"], horizontal=True)
    spc_haz_map = {"Categorical": "cat", "Tornado": "torn", "Wind": "wind", "Hail": "hail"}
    spc_haz_code = spc_haz_map[spc_view_hazard]
    
    spc_geojson = None
    if spc_day_num > 3:
        st.error(f"❌ You have selected Day {spc_day_num}. Please select a date within the Day 1-3 window.")
    else:
        spc_geojson = get_spc_geojson(d_str, spc_haz_code)
    
    if spc_day_num == 1: spc_title_prefix = f"DAY 1 SPC {spc_view_hazard.upper()}"
    elif spc_day_num == 2: spc_title_prefix = f"DAY 2 SPC {spc_view_hazard.upper()}"
    elif spc_day_num == 3: spc_title_prefix = f"DAY 3 SPC {spc_view_hazard.upper()}" if spc_view_hazard == "Categorical" else "DAY 3 SPC SEVERE PROBABILITY"
    else: spc_title_prefix = f"HISTORICAL SPC {spc_view_hazard.upper()}"

    spc_issue_str = ""
    if spc_geojson and spc_geojson.get('features'):
        props = spc_geojson['features'][0].get('properties', {})
        raw_issue = str(props.get('ISSUE', ''))
        if raw_issue and len(raw_issue) == 12 and raw_issue.isdigit():
            try:
                dt_utc = pd.to_datetime(raw_issue, format='%Y%m%d%H%M').tz_localize('UTC')
                dt_ct = dt_utc.tz_convert('US/Central')
                spc_issue_str = f"<br><span style='font-size: 13px; font-weight: normal; color: #cccccc;'>ISSUED: {dt_ct.strftime('%H:%M')} CT {dt_ct.strftime('%m/%d/%Y')}</span>"
            except:
                pass
    
    # --- THE FIX: BUMPER COLUMNS TO CONSTRAIN THE WIDTH ---
    col_spacer_l_spc, col_map_spc, col_right_spc, col_spacer_r_spc = st.columns([1, 5, 1.5, 1])
    
    with col_map_spc:
        m_spc = folium.Map(location=map_center, zoom_start=zoom, tiles=None)
        folium.TileLayer(base_tileset, cross_origin=True, crossOrigin=True).add_to(m_spc)

        title_html_spc = f'''
            <div style="position: absolute; top: 15px; left: 50%; transform: translateX(-50%);
            background: rgba(0, 32, 78, 0.85); backdrop-filter: blur(5px); border: 2px solid white; color: white;
            padding: 8px 20px; border-radius: 8px; font-family: 'Special Elite', monospace !important;
            font-size: 18px; font-weight: bold; text-align: center; z-index: 1000; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
            {spc_title_prefix} VALID {valid_date_formatted}
            {spc_issue_str}
            <br><span style='font-size: 14px; color: #ffcc00; font-weight: bold;'>⚠️ EXPERIMENTAL AND NOT SPC ⚠️</span>
            </div>
        '''
        m_spc.get_root().html.add_child(folium.Element(title_html_spc))

        if spc_view_hazard == "Categorical":
            spc_bank = CAT_COLORS
        elif spc_view_hazard == "Tornado":
            spc_bank = TOR_COLORS
        else:
            spc_bank = WIND_HAIL_COLORS
        legend_html_spc = build_map_legend(spc_view_hazard, spc_bank)
        m_spc.get_root().html.add_child(folium.Element(legend_html_spc))
        
        if spc_geojson and spc_day_num <= 8:
            valid_features = [f for f in spc_geojson.get('features', []) if f.get('geometry') and f['geometry'].get('coordinates')]
            if valid_features:
                spc_geojson['features'] = valid_features
                has_label = 'LABEL' in valid_features[0].get('properties', {})
                if has_label:
                    folium.GeoJson(spc_geojson, style_function=lambda x: {'fillColor': x['properties'].get('fill', '#ff0000'), 'color': x['properties'].get('stroke', '#ffffff'), 'fillOpacity': 0.4, 'weight': 2}, tooltip=folium.GeoJsonTooltip(fields=['LABEL'], aliases=['Risk:'], style="font-family: 'Special Elite', monospace;")).add_to(m_spc)
                else:
                    folium.GeoJson(spc_geojson, style_function=lambda x: {'fillColor': x['properties'].get('fill', '#ff0000'), 'color': x['properties'].get('stroke', '#ffffff'), 'fillOpacity': 0.4, 'weight': 2}).add_to(m_spc)
            else:
                st.info(f"🟢 No active {spc_view_hazard} areas were found in the official SPC outlook for this date.")

        apply_overlay_hide(m_spc)
        # --- THE FIX: USE CONTAINER WIDTH RE-ENABLED INSIDE BUMPERS ---
        st_folium(m_spc, use_container_width=True, height=700, key=f"spc_map_{st.session_state['map_key']}_{valid_date_formatted}_{spc_view_hazard}_{map_theme}_{st.session_state['hide_overlays']}")

    with col_right_spc:
        btn_text_spc = "👁️ Display All Overlays" if st.session_state['hide_overlays'] else "👁️ Hide Overlays for Image"
        if st.button(btn_text_spc, use_container_width=True, key="toggle_t3"):
            st.session_state['hide_overlays'] = not st.session_state['hide_overlays']
            st.rerun()

    render_help_instructions()

# ==========================================
# TAB 4: FORECAST ANALYTICS (HISTORY)
# ==========================================
with tab_analytics:
    st.header(f"📈 {st.session_state['authenticated_user'].capitalize()}'s Historical Trends")
    
    # --- HELPER TO DRAW RELIABILITY DIAGRAM ---
    def draw_reliability_diagram(hazard_df, hazard_name, chart_theme):
        if hazard_df.empty: return None
        
        # Group by Forecast Probability and calculate the mean Observed Coverage
        grouped = hazard_df.groupby('Forecast_Prob')['Obs_Coverage'].mean().reset_index()
        grouped = grouped.sort_values(by='Forecast_Prob')
        
        fig = go.Figure()
        
        # Draw the "Perfect Reliability" diagonal line
        fig.add_trace(go.Scatter(
            x=[0, 100], y=[0, 100], 
            mode='lines', 
            name='Perfect Calibration', 
            line=dict(color='gray', dash='dash', width=2)
        ))
        
        # Draw the User's Actual Bias
        fig.add_trace(go.Scatter(
            x=grouped['Forecast_Prob'], y=grouped['Obs_Coverage'], 
            mode='lines+markers', 
            name='Your Bias', 
            marker=dict(size=12, color='#FF4B4B', line=dict(width=2, color='white')),
            line=dict(color='#FF4B4B', width=3)
        ))
        
        # Formatting
        fig.update_layout(
            title=f"{hazard_name} Reliability Curve",
            xaxis_title="Forecast Probability (%)",
            yaxis_title="Observed Coverage (%)",
            xaxis=dict(range=[-5, 105], dtick=15),
            yaxis=dict(range=[-5, 105], dtick=15),
            template='plotly_dark' if chart_theme == "Dark Mode" else 'plotly_white',
            margin=dict(l=20, r=20, t=50, b=20),
            height=400
        )
        return fig
    
    if os.path.exists(user_history_file):
        try:
            df_history = pd.read_csv(user_history_file)
            
            # Catch old CSV schemas and enforce wipe
            if 'Forecast_Prob' not in df_history.columns or 'Obs_Coverage' not in df_history.columns:
                st.error("⚠️ Outdated Data Detected: Your database is missing the required raw metrics for Reliability Plotting.")
                st.warning("Please click 'Erase MY Analytics History' below to upgrade your database to the new engine.")
            else:
                cat_df = df_history[df_history['Hazard'].str.contains("ALL", case=False, na=False)]
                tor_df = df_history[df_history['Hazard'].str.contains("TORNADO", case=False, na=False)]
                wind_df = df_history[df_history['Hazard'].str.contains("WIND", case=False, na=False)]
                hail_df = df_history[df_history['Hazard'].str.contains("HAIL", case=False, na=False)]

                # --- SUB-TABS FOR CLEANER LAYOUT ---
                tab_tor, tab_wind, tab_hail, tab_cat = st.tabs(["🌪️ Tornado", "💨 Wind", "🧊 Hail", "🌩️ Categorical"])

                def render_analytics_tab(title, data):
                    if not data.empty:
                        # 1. Full-Width Metrics
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Avg Calibration", f"{data['Cal_Score'].mean():.1f}%")
                        c2.metric("Avg Threat (CSI)", f"{data['CSI'].mean():.1f}%")
                        c3.metric("Avg POD", f"{data['POD'].mean():.1f}%")
                        c4.metric("Avg FAR", f"{data['FAR'].mean():.1f}%")
                        
                        st.markdown("---")
                        
                        # 2. Full-Width Chart & Explanation
                        col_chart, col_empty = st.columns([3, 1])
                        with col_chart:
                            st.info("**💡 How to read this graph:**\n* **The Dotted Line:** Perfect calibration (your forecast matched reality exactly).\n* **Dots BELOW the line:** You are *over-forecasting* (expecting more storms than actually happen).\n* **Dots ABOVE the line:** You are *under-forecasting* (storms are more widespread than you expected).")
                            
                            fig = draw_reliability_diagram(data, title, map_theme)
                            if fig:
                                st.plotly_chart(fig, use_container_width=True)
                                
                        # 3. Cleaned Up Data Table (COLLAPSIBLE BY DATE)
                        st.markdown(f"### 📂 Raw {title} Forecast Logs")
                        
                        clean_df = data.copy()
                        # Round the numbers to look clean
                        for col in ['Forecast_Prob', 'Obs_Coverage', 'Cal_Score', 'CSI', 'POD', 'FAR']:
                            if col in clean_df.columns: clean_df[col] = clean_df[col].round(1)
                        
                        # Sort dates so the newest forecasts are on top
                        unique_dates = sorted(clean_df['Date'].unique(), reverse=True)
                        
                        for d in unique_dates:
                            day_data = clean_df[clean_df['Date'] == d]
                            
                            # Make each individual day its own dropdown
                            with st.expander(f"📅 Event Date: {d}"):
                                d_col1, d_col2 = st.columns([5, 1])
                                
                                with d_col1:
                                    st.dataframe(day_data[['Forecast_Prob', 'Obs_Coverage', 'Cal_Score', 'CSI', 'POD', 'FAR']], hide_index=True, use_container_width=True)
                                
                                with d_col2:
                                    # Specific Delete Button for this Date & Hazard
                                    if st.button(f"🗑️ Delete", key=f"del_{title}_{d}", use_container_width=True):
                                        full_df = pd.read_csv(user_history_file)
                                        hazard_str = "ALL" if title == "Categorical" else title.upper()
                                        
                                        # Filter out this exact date and hazard combination from the database
                                        mask = ~((full_df['Date'] == d) & (full_df['Hazard'].str.contains(hazard_str, case=False, na=False)))
                                        full_df[mask].to_csv(user_history_file, index=False)
                                        
                                        st.success(f"Deleted {d}!")
                                        time.sleep(0.5)
                                        st.rerun()
                    else: 
                        st.info(f"No forecasts logged for {title} yet.")

                with tab_tor: render_analytics_tab("Tornado", tor_df)
                with tab_wind: render_analytics_tab("Wind", wind_df)
                with tab_hail: render_analytics_tab("Hail", hail_df)
                with tab_cat: render_analytics_tab("Categorical", cat_df)
                    
        except Exception as e: 
            st.error(f"Error reading database: {e}")
            
        st.markdown("---")
        if st.button("🗑️ Erase MY Analytics History", type="secondary"):
            os.remove(user_history_file)
            st.success("Your personal history has been completely wiped.")
            st.rerun()
    else: 
        st.info("You haven't logged any personal forecasts yet. Verify a forecast to start building your Reliability Diagrams!")

with tab_about:
    st.header("📖 About Doodles' Forecast Lab")
    st.markdown("Welcome to the official documentation for the Doodles' Weather Updates Forecast Lab. This tool provides storm chasers and meteorologists with an experimental platform to create, log, and mathematically verify severe weather forecasts using National Weather Service standards.")
    
    st.markdown("---")
    
    st.subheader("🧮 How the Scoring Works (The Simple Version)")
    st.markdown("""
    Think of your forecast polygon as a warning area you draw on a map to highlight where severe storms will hit. Because weather is unpredictable, the app draws a 25-mile "danger zone" bubble around every actual storm report to create a verified target area.
    
    * **Calibration Score (The Oddsmaker):** This grades how well you predicted the *chances* of a storm. If you draw a 15% risk area, the app checks if exactly 15% of your drawn shape was actually filled with storms. If you guessed the odds perfectly, you score a 100%.
    * **FAR (False Alarm Ratio - The "Crying Wolf" Score):** This measures how much of your forecast area was just empty space. If you draw a massive risk area covering a whole state, but storms only happen in one small city, your False Alarm Ratio will be high because most of your shape saw calm weather.
    * **CSI (Critical Success Index - The "Threat Score"):** This is the ultimate grade for your forecast. It heavily punishes you if your shape is too small (you missed the storms) AND if your shape is too big (you had too many false alarms). To get a high Critical Success Index, your forecast area needs to be *just the right size* and in *just the right spot*.
    """)
    
    with st.expander("🔽 See More: The Advanced NWS Mathematics"):
        st.info("""
        **1. The Observed Footprint:** The engine buffers every valid Local Storm Report (LSR) and Damage Assessment Toolkit (DAT) track by exactly 0.36 degrees (~25 miles / 40km) to create a verified, continuous "Hazard Footprint."
        
        **2. Calibration Formula:**
        * *If you over-forecasted (fewer storms than expected):*
            `CS = (Observed Coverage % / Forecast Probability %) * 100`
        * *If you under-forecasted (more storms than expected):*
            `CS = (Forecast Probability % / Observed Coverage %) * 100`
        
        **3. NWS Threat Score Formulas (Area-Based):**
        * **POD (Probability of Detection):** `Intersection Area / Observed Area`
        * **FAR (False Alarm Ratio):** `(Forecast Area - Intersection Area) / Forecast Area`
        * **CSI (Critical Success Index):** `Intersection Area / (Forecast Area + Observed Area - Intersection Area)`
        """)

    st.markdown("---")
    st.subheader("📡 Data Sources & Credits")
    st.markdown("""
    This lab pulls live, geospatial data from official government and academic servers:
    * **Live LSR Data:** Pulled via API from the [Iowa Environmental Mesonet (IEM)](https://mesonet.agron.iastate.edu/).
    * **Official Tornado Tracks:** Queried directly from the [NOAA NWS Damage Assessment Toolkit (DAT) Feature Server](https://apps.dat.noaa.gov/stormdamage/damageviewer/).
    * **Reference Polygons:** Fetched from the [NOAA Storm Prediction Center (SPC)](https://www.spc.noaa.gov/) official GeoJSON product feeds.
    """)