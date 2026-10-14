"""
Frontend - Results View
Detailed inspection of current execution outcome, execution checklist, verification, and logs.
"""

import os
import streamlit as st
from utils.logger import SESSION_LOGS


def render_results_view(user: dict):
    """Renders latest execution result and logs."""
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 style="color: #f8fafc; font-size: 28px; font-weight: 800; margin-bottom: 4px;">
            📊 Execution Results & Logs
        </h1>
        <p style="color: #94a3b8; font-size: 14px;">
            Detailed inspection of browser automation results, verification status, and runtime logs.
        </p>
    </div>
    """, unsafe_allow_html=True)

    res = st.session_state.get("execution_result")

    if not res:
        st.info("No active execution result in this session. Execute a workflow on the **Dashboard** first.")
        return

    # Products and Excel Data
    products = res.get("products") or res.get("extracted_data", {}).get("products") or st.session_state.get("product_results") or []
    excel_path = res.get("excel_file") or res.get("extracted_data", {}).get("excel_file") or st.session_state.get("generated_excel")

    # 1. EXECUTION STATUS
    with st.container(border=True):
        st.subheader("Execution Status")
        if res.get("status") == "WAITING_CONFIRMATION":
            st.warning(f"⏸️ {res.get('summary')}")
        elif res.get("success"):
            st.success(f"✓ {res.get('summary', 'Workflow completed successfully')}")
        else:
            st.error(f"❌ {res.get('summary', 'Workflow execution failed')}")
            col_fail1, col_fail2 = st.columns(2)
            with col_fail1:
                st.markdown(f"**Failed Step:** Step {res.get('completed_steps', 0) + 1} of {res.get('total_steps', 0)}")
            with col_fail2:
                st.markdown(f"**Error Details:** `{res.get('error', 'Unknown error')}`")

        # Applications
        apps = res.get("applications", [])
        if apps:
            app_badges = " ".join([f"<span style='background:#1e3a8a;color:#93c5fd;padding:3px 8px;border-radius:8px;font-size:12px;margin-right:6px;'>{a}</span>" for a in apps])
            st.markdown(f"**Applications Used:** {app_badges}", unsafe_allow_html=True)
            st.write("")

        col1, col2, col3 = st.columns(3)
        col1.metric("Status", res.get("status", "SUCCESS" if res.get("success") else "FAILED"))
        col2.metric("Completed Steps", f"{res.get('completed_steps', 0)} / {res.get('total_steps', 0)}")
        col3.metric("Duration", f"{res.get('execution_time', 0)}s")

        # Execution Checklist
        exec_checklist = res.get("execution_checklist", [])
        if exec_checklist:
            st.markdown("#### ⚙️ Step-by-Step Execution")
            for itm in exec_checklist:
                st.markdown(f"<span style='color:#6ee7b7;'>{itm}</span>", unsafe_allow_html=True)
            st.write("")

        # Verification Checklist
        verif_items = res.get("verification_items", [])
        if verif_items:
            st.markdown("#### 🛡️ Verification Status")
            for v in verif_items:
                color = "#6ee7b7" if v.startswith("✓") else "#fca5a5"
                st.markdown(f"<span style='color:{color}; font-weight:600;'>{v}</span>", unsafe_allow_html=True)
            st.write("")

        # Email-specific execution evidence and previews.
        email_context = res.get("context", {}) or {}
        email_results = res.get("email_results") or email_context.get("email_results") or []
        email_summary = res.get("email_summary") or email_context.get("email_summary") or {}
        reminders = email_context.get("reminders") or []
        email_messages = email_context.get("email_messages") or []
        if reminders or email_results or email_messages:
            st.markdown("#### 📧 Email Automation Details")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Prepared", email_summary.get("prepared", len(reminders)))
            c2.metric("Submitted", email_summary.get("submitted", email_summary.get("sent", sum(1 for x in email_results if x.get("status") in ("SENT", "SIMULATED")))))
            c3.metric("Failed", email_summary.get("failed", sum(1 for x in email_results if x.get("status") == "FAILED")))
            c4.metric("Skipped / Pending", email_summary.get("skipped", 0) + email_summary.get("pending_verification", 0))
            provider_info = email_context.get("email_provider") or {}
            if provider_info:
                label = "connected" if provider_info.get("connected") else "not connected"
                st.caption(f"Provider: {provider_info.get('provider', 'unknown')} ({label}). Submission evidence is not delivery evidence.")
            if reminders:
                st.markdown("**Reviewable previews**")
                for idx, preview in enumerate(reminders, 1):
                    with st.expander(f"{idx}. {preview.get('to') or 'Missing recipient'} · {preview.get('subject', '(no subject)')} · {preview.get('status', 'PREVIEW')}"):
                        st.caption(f"Attachments: {', '.join(os.path.basename(str(x)) for x in preview.get('attachments', []) or ([preview.get('attachment')] if preview.get('attachment') else [])) or 'None'}")
                        if preview.get("validation_errors"):
                            st.error("; ".join(preview["validation_errors"]))
                        st.text(preview.get("body", ""))
            for result in email_results:
                evidence = result.get("provider_message_id") or result.get("email_id") or result.get("error") or result.get("skip_reason") or "No evidence"
                st.caption(f"{result.get('status', 'UNKNOWN')}: {result.get('to', 'unknown recipient')} · {evidence}")

    # 2. ACTIVITY LOGS
    st.markdown("### 📋 Activity Logs")
    with st.container(border=True):
        if not SESSION_LOGS:
            st.caption("No log entries recorded yet.")
        else:
            log_text = "\n".join(SESSION_LOGS[-60:])
            st.code(log_text, language="log")

    # 3. PRODUCT SEARCH RESULTS TABLE
    if products:
        st.markdown("### 🛒 Product Search Results")
        with st.container(border=True):
            st.markdown(f"**Found {len(products)} authentic product listings across shopping websites:**")

            # Format table data
            table_rows = []
            for idx, p in enumerate(products, 1):
                link_url = p.get("Product Link", "")
                link_md = f"[View Product]({link_url})" if (link_url and link_url != "N/A" and link_url.startswith("http")) else "N/A"
                table_rows.append({
                    "#": idx,
                    "Product Name": p.get("Product Name", "N/A"),
                    "Website": p.get("Website", "N/A"),
                    "Price": p.get("Price", "N/A"),
                    "Rating": p.get("Rating", "N/A"),
                    "Product Link": link_md
                })

            # Display table with markdown links support
            st.markdown(
                "| # | Product Name | Website | Price | Rating | Product Link |\n"
                "|---|---|---|---|---|---|\n" +
                "\n".join([
                    f"| {r['#']} | {r['Product Name']} | **{r['Website']}** | <span style='color:#6ee7b7; font-weight:700;'>{r['Price']}</span> | {r['Rating']} | {r['Product Link']} |"
                    for r in table_rows
                ]),
                unsafe_allow_html=True
            )
            st.write("")

    # 4. EXCEL REPORT (AUTOMATICALLY GENERATED)
    if excel_path and os.path.exists(excel_path):
        st.markdown("### 📊 Excel Report")
        with st.container(border=True):
            f_size = os.path.getsize(excel_path)
            f_name = os.path.basename(excel_path)
            st.caption(f"✓ Product search report generated automatically by WorkPilot ({f_name}, {f_size:,} bytes)")

            try:
                with open(excel_path, "rb") as f:
                    excel_bytes = f.read()

                col_dl1, col_dl2 = st.columns([2, 4])
                with col_dl1:
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=excel_bytes,
                        file_name=f_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                with col_dl2:
                    st.markdown(f"<span style='font-size:12px; color:#94a3b8; line-height:36px;'>Contains all {len(products)} extracted products with formatted prices, columns, and clickable links.</span>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error loading Excel file: {e}")

    # 5. FINAL EXECUTION SCREENSHOT (OR FAILURE SCREENSHOT)
    shot_path = st.session_state.get("execution_screenshot")
    if not shot_path and res:
        shot_path = res.get("final_screenshot")

    if not res:
        st.markdown("### 📸 Final Execution Screenshot")
        with st.container(border=True):
            st.info("No execution screenshot available yet.")
    elif res.get("success"):
        st.markdown("### 📸 Final Execution Screenshot")
        with st.container(border=True):
            if shot_path and os.path.exists(shot_path):
                st.caption(f"Captured automatically after successful execution ({os.path.basename(shot_path)})")
                st.image(shot_path, caption="Final Browser State", use_container_width=True)
            else:
                st.info("No execution screenshot available yet.")
    else:
        st.markdown("### 📸 Screenshot at Failure")
        with st.container(border=True):
            if shot_path and os.path.exists(shot_path):
                st.caption(f"Captured automatically at point of failure ({os.path.basename(shot_path)})")
                st.image(shot_path, caption="Browser State at Failure", use_container_width=True)
            else:
                st.info("No execution screenshot available yet.")
