"""
WorkPilot – Natural Language Workflow Automation System
Main Streamlit Application Entrypoint
"""

import streamlit as st
from frontend.login import render_login_view
from frontend.dashboard import render_dashboard_view
from frontend.history import render_history_view
from frontend.results import render_results_view

# Configure Streamlit Page
st.set_page_config(
    page_title="WorkPilot – Workflow Automation",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .stApp {
        background-color: #0b1020;
        color: #e5e7eb;
    }
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #26324a;
    }
    .brand-title {
        font-size: 22px;
        font-weight: 800;
        color: #f8fafc;
    }
    .brand-sub {
        font-size: 12px;
        color: #94a3b8;
        margin-bottom: 20px;
    }
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None

if "current_prompt" not in st.session_state:
    st.session_state.current_prompt = ""

if "planned_workflow" not in st.session_state:
    st.session_state.planned_workflow = None

if "execution_result" not in st.session_state:
    st.session_state.execution_result = None

if "execution_screenshot" not in st.session_state:
    st.session_state.execution_screenshot = None

if "workflow_status" not in st.session_state:
    st.session_state.workflow_status = "READY"

if "product_results" not in st.session_state:
    st.session_state.product_results = None

if "generated_excel" not in st.session_state:
    st.session_state.generated_excel = None


# Router: Show Login or Authenticated Dashboard
user = st.session_state.authenticated_user

if not user:
    render_login_view()
else:
    # Sidebar Navigation
    with st.sidebar:
        st.markdown(f"""
        <div class="brand-title">🌐 WorkPilot</div>
        <div class="brand-sub">Natural Language Browser Workflows</div>
        <div style="background:#1e293b;padding:10px 12px;border-radius:8px;margin-bottom:15px;font-size:12px;color:#94a3b8;">
            Logged in as:<br><strong style="color:#f8fafc;">{user.get('name', 'User')}</strong><br>
            <span style="font-size:11px;">{user.get('email', '')}</span>
        </div>
        """, unsafe_allow_html=True)

        nav_selection = st.radio(
            "Navigation",
            ["Dashboard", "Workflow History", "Results", "Logout"],
            label_visibility="collapsed"
        )

        st.divider()
        st.caption("Powered by Ollama, LangGraph, Selenium & Firebase")

    if nav_selection == "Dashboard":
        render_dashboard_view(user)

    elif nav_selection == "Workflow History":
        render_history_view(user)

    elif nav_selection == "Results":
        render_results_view(user)

    elif nav_selection == "Logout":
        st.session_state.authenticated_user = None
        st.session_state.planned_workflow = None
        st.session_state.execution_result = None
        st.session_state.execution_screenshot = None
        st.session_state.product_results = None
        st.session_state.generated_excel = None
        st.success("You have been logged out.")
        st.rerun()
