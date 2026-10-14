"""
Frontend - Firebase Authentication View (Sign In & Sign Up)
"""

import streamlit as st
from firebase.auth import sign_in_user, sign_up_user
from firebase.firebase_config import is_firebase_configured


def render_login_view():
    """Renders clean login and signup interface."""
    st.markdown("""
    <div style="text-align: center; margin-top: 30px; margin-bottom: 25px;">
        <h1 style="color: #f8fafc; font-size: 32px; font-weight: 800; margin-bottom: 6px;">
            🌐 WorkPilot
        </h1>
        <p style="color: #94a3b8; font-size: 15px;">
            Sign in to start automating your browser with natural language.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if not is_firebase_configured():
        st.info(
            "ℹ️ **Firebase Status**: No Firebase service account or API key found in `.env`. "
            "Running in **Local Authentication Mode** for instant local testing and viva demonstration."
        )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.container(border=True):
            tab_login, tab_signup = st.tabs(["🔑 Sign In", "📝 Create Account"])

            with tab_login:
                with st.form("login_form", clear_on_submit=False):
                    email = st.text_input("Email Address", placeholder="student@example.com")
                    password = st.text_input("Password", type="password", placeholder="••••••••")
                    submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

                    if submitted:
                        if not email or not password:
                            st.error("Please enter both email and password.")
                        else:
                            with st.spinner("Authenticating..."):
                                success, user_data, msg = sign_in_user(email, password)
                                if success:
                                    st.session_state.authenticated_user = user_data
                                    st.success("Login successful!")
                                    st.rerun()
                                else:
                                    st.error(msg)

            with tab_signup:
                with st.form("signup_form", clear_on_submit=False):
                    name = st.text_input("Full Name", placeholder="Alex Smith")
                    reg_email = st.text_input("Email Address", placeholder="alex@example.com")
                    reg_password = st.text_input("Password", type="password", placeholder="Minimum 6 characters")
                    reg_submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

                    if reg_submitted:
                        if not name or not reg_email or not reg_password:
                            st.error("All fields are required.")
                        else:
                            with st.spinner("Creating account..."):
                                success, user_data, msg = sign_up_user(reg_email, reg_password, name)
                                if success:
                                    st.session_state.authenticated_user = user_data
                                    st.success(f"Welcome {name}! {msg}")
                                    st.rerun()
                                else:
                                    st.error(msg)
