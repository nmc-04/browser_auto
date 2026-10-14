"""
Frontend - Workflow History View
Fetches user-specific workflows and execution runs from Firestore with multi-application metrics.
"""

import os
import streamlit as st
from firebase.database import get_user_executions, get_user_workflows


def render_history_view(user: dict):
    """Renders user execution history."""
    user_id = user.get("user_id", "anonymous")

    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 style="color: #f8fafc; font-size: 28px; font-weight: 800; margin-bottom: 4px;">
            📜 Workflow Execution History
        </h1>
        <p style="color: #94a3b8; font-size: 14px;">
            View past automation executions, application steps, and verification results stored in Firebase Firestore.
        </p>
    </div>
    """, unsafe_allow_html=True)

    executions = get_user_executions(user_id)
    workflows = {w.get("workflow_id"): w for w in get_user_workflows(user_id)}

    if not executions:
        st.info("No recorded executions found for your account yet. Go to the **Dashboard** to run a task!")
        return

    st.caption(f"Showing {len(executions)} past execution(s) for user `{user.get('email', user_id)}`.")

    for item in executions:
        status = item.get("status", "UNKNOWN")
        is_success = status in ("COMPLETED", "SUCCESS")
        status_color = "#6ee7b7" if is_success else ("#fbbf24" if status == "WAITING_CONFIRMATION" else "#fca5a5")
        status_bg = "#123c35" if is_success else ("#2a2115" if status == "WAITING_CONFIRMATION" else "#451a1a")

        wf_id = item.get("workflow_id")
        matched_wf = workflows.get(wf_id, {})
        wf_name = matched_wf.get("workflow_name") or "Automated Workflow"
        prompt_text = matched_wf.get("prompt") or ""
        apps = item.get("applications") or matched_wf.get("applications", [])

        time_str = item.get("started_at", "N/A")[:19].replace("T", " ")
        completed = item.get("completed_steps", 0)
        total = item.get("total_steps", 0)
        duration = item.get("execution_time", 0.0)

        with st.container(border=True):
            col_info, col_status = st.columns([4, 1])

            with col_info:
                st.markdown(f"#### 🌐 {wf_name}")
                if prompt_text:
                    st.caption(f"Prompt: \"{prompt_text}\"")
                st.caption(f"Execution ID: `{item.get('execution_id')}` • Date: {time_str}")

            with col_status:
                st.markdown(
                    f'<div style="background:{status_bg};color:{status_color};padding:6px 10px;border-radius:10px;text-align:center;font-weight:700;font-size:12px;">● {status}</div>',
                    unsafe_allow_html=True
                )

            # Application Badges
            if apps:
                app_badges = " ".join([f"<span style='background:#1e3a8a;color:#93c5fd;padding:2px 7px;border-radius:6px;font-size:11px;margin-right:4px;'>{a}</span>" for a in apps])
                st.markdown(f"**Applications:** {app_badges}", unsafe_allow_html=True)

            m1, m2, m3 = st.columns(3)
            m1.markdown(f"**Steps**: {completed}/{total}")
            m2.markdown(f"**Duration**: {duration}s")
            m3.markdown(f"**Failed Step**: {item.get('failed_step') or 'None'}")

            if item.get("error_message"):
                st.error(f"Error: {item.get('error_message')}")

            email_summary = item.get("email_summary") or {}
            email_results = item.get("email_results") or []
            if email_summary or email_results:
                st.markdown(
                    f"**Email results:** prepared {email_summary.get('prepared', 0)} · submitted {email_summary.get('submitted', email_summary.get('sent', 0))} · "
                    f"failed {email_summary.get('failed', 0)} · pending {email_summary.get('pending_verification', 0)} · skipped {email_summary.get('skipped', 0)}"
                )
                with st.expander("📧 Inspect email evidence"):
                    for result in email_results:
                        evidence = result.get("provider_message_id") or result.get("email_id") or result.get("error") or result.get("skip_reason") or "No evidence"
                        st.caption(f"{result.get('status', 'UNKNOWN')}: {result.get('to', 'unknown recipient')} · {result.get('subject', '(no subject)')} · {evidence}")

            # Show screenshots if any
            screenshots = item.get("screenshots", [])
            if screenshots:
                with st.expander("🖼️ View Screenshots"):
                    cols = st.columns(min(len(screenshots), 3))
                    for idx, img_path in enumerate(screenshots):
                        with cols[idx % len(cols)]:
                            if img_path.startswith("data:image") or img_path.startswith("http") or os.path.exists(img_path):
                                st.image(img_path, caption=f"Screenshot {idx+1}", use_container_width=True)
