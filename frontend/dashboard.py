"""
Frontend - Dashboard View (Task Input, Workflow Review & Execution)
Supports Browser (Selenium) and Enterprise Cross-Application Workflows with Human Confirmation & Verification.
"""

import os
import streamlit as st
from backend.workflow_executor import plan_workflow, execute_workflow_run
from backend.email_tool import get_email_connection_status, connect_gmail
from utils.logger import SESSION_LOGS, clear_session_logs


def render_dashboard_view(user: dict):
    """Renders the main task automation dashboard."""
    user_id = user.get("user_id", "anonymous")
    user_name = user.get("name", "User")

    # Email account status stays in the existing dashboard.  OAuth is the only
    # Gmail credential flow; passwords and tokens are never collected here.
    with st.expander("📧 Email automation connection", expanded=False):
        email_status = get_email_connection_status()
        status_label = "Connected" if email_status.get("connected") else "Not connected"
        st.markdown(f"**Provider:** `{email_status.get('provider', 'unknown')}`  ·  **Status:** `{status_label}`")
        if email_status.get("account"):
            st.caption(f"Authorized account: {email_status['account']}")
        st.caption(email_status.get("message") or email_status.get("reason", ""))
        if email_status.get("mode") == "gmail" and not email_status.get("connected"):
            if st.button("Connect Gmail with OAuth", key="connect_gmail"):
                try:
                    connection = connect_gmail()
                    if connection.get("connected"):
                        st.success(connection.get("message", "Gmail connected."))
                    else:
                        st.error(connection.get("message", "Gmail could not be connected."))
                except Exception as exc:
                    st.error(f"Gmail connection failed: {exc}")
        elif email_status.get("mode") == "demo":
            st.info("Demo mode records messages locally and never sends external email. Set EMAIL_PROVIDER=gmail and configure OAuth for real sending.")

    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 style="color: #f8fafc; font-size: 30px; font-weight: 800; margin-bottom: 4px;">
            WorkPilot
        </h1>
        <p style="color: #94a3b8; font-size: 15px;">
            Autonomous AI work agent for browser and enterprise workflow automation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Status pill in top corner
    current_status = st.session_state.get("workflow_status", "READY")
    status_bg = "#123c35" if current_status in ("READY", "COMPLETED") else ("#2a2115" if current_status in ("RUNNING", "WAITING_CONFIRMATION") else "#451a1a")
    status_color = "#6ee7b7" if current_status in ("READY", "COMPLETED") else ("#fbbf24" if current_status in ("RUNNING", "WAITING_CONFIRMATION") else "#fca5a5")

    # Step 1: Prompt Input Container
    with st.container(border=True):
        st.markdown("### 1. Natural Language Task")
        st.caption("Describe the employee, browser, or business task you want to automate in simple words.")

        default_prompt = st.session_state.get("current_prompt", "Process all unpaid invoices.")
        prompt_input = st.text_area(
            "Task instruction",
            value=default_prompt,
            height=90,
            label_visibility="collapsed",
            placeholder="e.g. Process all unpaid invoices and send reminders with invoice attached."
        )

        # Quick Example Buttons - 5 Major Enterprise Demonstrations
        st.markdown("<span style='font-size: 13px; font-weight: 700; color: #38bdf8;'>🚀 Five Major Demonstrations:</span>", unsafe_allow_html=True)
        col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)

        if col_d1.button("💼 Daily Work", use_container_width=True, help="Demo 1: Handle my work for today"):
            st.session_state.current_prompt = "Handle my work for today."
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.rerun()

        if col_d2.button("📑 Invoices", use_container_width=True, help="Demo 2: Process all unpaid invoices"):
            st.session_state.current_prompt = "Process all unpaid invoices."
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.rerun()

        if col_d3.button("🛒 Procurement", use_container_width=True, help="Demo 3: Order office supplies in spreadsheet"):
            st.session_state.current_prompt = "Order the office supplies in this spreadsheet."
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.rerun()

        if col_d4.button("📅 Meeting Brief", use_container_width=True, help="Demo 4: Prepare for my 3 PM client meeting"):
            st.session_state.current_prompt = "Prepare for my 3 PM client meeting."
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.rerun()

        if col_d5.button("📊 Activity Report", use_container_width=True, help="Demo 5: Prepare this month's employee activity report"):
            st.session_state.current_prompt = "Prepare this month's employee activity report."
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.rerun()

        # Product Search & Automated Excel Report Examples
        st.markdown("<span style='font-size: 13px; font-weight: 700; color: #38bdf8;'>🛍️ Product Search & Automatic Excel Report:</span>", unsafe_allow_html=True)
        col_p1, col_p2, col_p3 = st.columns(3)

        if col_p1.button("💻 Laptops < ₹60k", use_container_width=True, help="Search for laptops under ₹60,000"):
            st.session_state.current_prompt = "Search for laptops under ₹60,000"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        if col_p2.button("📱 10 Phones < ₹30k", use_container_width=True, help="Find 10 smartphones under ₹30,000"):
            st.session_state.current_prompt = "Find 10 smartphones under ₹30,000"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        if col_p3.button("⚖️ Compare iPhone 16", use_container_width=True, help="Compare iPhone 16 prices"):
            st.session_state.current_prompt = "Compare iPhone 16 prices"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        # Browser Automation Examples
        st.markdown("<span style='font-size: 12px; color: #94a3b8;'>Other Browser Tasks:</span>", unsafe_allow_html=True)
        col_e1, col_e2, col_e3, col_e4 = st.columns(4)

        if col_e1.button("📝 Demo Form", use_container_width=True):
            st.session_state.current_prompt = "Open demo_site/form.html, enter Alice Smith as name, alice@example.com as email, select Female, and click submit"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        if col_e2.button("🔍 Google Search", use_container_width=True):
            st.session_state.current_prompt = "Open https://www.google.com and search for Selenium tutorials"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        if col_e3.button("📚 Wikipedia", use_container_width=True):
            st.session_state.current_prompt = "Open https://www.wikipedia.org, type Artificial Intelligence in search_box, and click search_button"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        if col_e4.button("⚠️ Clarification", use_container_width=True):
            st.session_state.current_prompt = "Enter John into the name field and submit"
            st.session_state.planned_workflow = None
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            st.rerun()

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            gen_clicked = st.button("✨ Generate Workflow", type="primary", use_container_width=True)
        with col_btn2:
            if st.button("Clear", use_container_width=False):
                st.session_state.current_prompt = ""
                st.session_state.planned_workflow = None
                st.session_state.execution_result = None
                st.session_state.execution_screenshot = None
                st.session_state.product_results = None
                st.session_state.generated_excel = None
                st.session_state.workflow_status = "READY"
                clear_session_logs()
                st.rerun()

    # Handle Generation
    if gen_clicked:
        if not prompt_input.strip():
            st.warning("Please enter a task description before generating workflow.")
        else:
            st.session_state.current_prompt = prompt_input.strip()
            st.session_state.execution_result = None
            st.session_state.execution_screenshot = None
            st.session_state.product_results = None
            st.session_state.generated_excel = None
            clear_session_logs()
            with st.spinner("Analyzing instruction and staging workflow..."):
                res = plan_workflow(prompt_input.strip(), user_id=user_id)
                if res["success"]:
                    st.session_state.planned_workflow = res["workflow"]
                    st.session_state.workflow_status = "READY"
                    st.session_state.generation_error = None
                else:
                    st.session_state.planned_workflow = res.get("workflow")
                    st.session_state.workflow_status = "FAILED"
                    st.session_state.generation_error = res.get("error")
                st.rerun()

    # Display Generation Errors / Clarifications
    if st.session_state.get("generation_error"):
        st.error(f"❌ {st.session_state.generation_error}")

    # Step 2: Generated Workflow Preview
    wf = st.session_state.get("planned_workflow")
    if wf and wf.steps:
        with st.container(border=True):
            head_col, status_badge_col = st.columns([4, 1])
            with head_col:
                st.markdown(f"### 2. Generated Workflow: {wf.workflow_name}")
                st.caption(f"LangGraph validated {len(wf.steps)} structured action(s).")
            with status_badge_col:
                st.markdown(
                    f'<div style="background:{status_bg};color:{status_color};padding:6px 12px;border-radius:12px;text-align:center;font-weight:700;font-size:12px;">● {current_status}</div>',
                    unsafe_allow_html=True
                )

            # Display Applications Involved
            apps = getattr(wf, "applications", [])
            if apps:
                app_badges = " ".join([f"<span style='background:#1e3a8a;color:#93c5fd;padding:3px 8px;border-radius:8px;font-size:12px;margin-right:6px;'>{a}</span>" for a in apps])
                st.markdown(f"**Applications Involved:** {app_badges}", unsafe_allow_html=True)
                st.write("")

            # Display Steps
            for idx, step in enumerate(wf.steps, start=1):
                col_num, col_info = st.columns([1, 15])
                with col_num:
                    st.markdown(f"<div style='background:#1d4ed8;color:white;width:28px;height:28px;line-height:28px;border-radius:50%;text-align:center;font-weight:700;font-size:13px;'>{idx}</div>", unsafe_allow_html=True)
                with col_info:
                    conf_tag = " <span style='background:#451a1a;color:#fca5a5;padding:2px 6px;border-radius:4px;font-size:11px;'>Requires Confirmation</span>" if getattr(step, "requires_confirmation", False) else ""
                    st.markdown(f"**{step.action.upper()}** &nbsp;—&nbsp; `{step.to_display_label()}`{conf_tag}", unsafe_allow_html=True)
                    if step.url:
                        st.caption(f"Target URL: {step.url}")
                    elif step.get_target_string():
                        st.caption(f"Target: `{step.get_target_string()}` | Parameter: `{step.value or 'N/A'}`")

            st.divider()

            # Human Confirmation Modal / Banner if required
            has_sensitive_step = any(getattr(s, "requires_confirmation", False) for s in wf.steps)
            is_confirmed = st.session_state.get("workflow_confirmed", False)

            if has_sensitive_step and not is_confirmed:
                st.warning("⚠️ **Human Confirmation Notice:** This workflow includes sensitive operations (e.g. dispatching external emails or staging purchase orders). Please review before running.")
                conf_c1, conf_c2 = st.columns([1, 4])
                with conf_c1:
                    if st.button("✓ Confirm & Authorize", type="secondary", use_container_width=True):
                        st.session_state.workflow_confirmed = True
                        st.rerun()

            # Run Controls
            col_run, col_opt1, col_opt2 = st.columns([2, 2, 2])
            with col_opt1:
                headless = st.checkbox("Run in background (Headless)", value=False, help="Uncheck to view Chrome browser window live during execution.")
            with col_opt2:
                timeout_val = st.slider("Wait Timeout (s)", min_value=5, max_value=30, value=15)

            with col_run:
                run_clicked = st.button("🚀 Run Workflow", type="primary", use_container_width=True)

            if run_clicked:
                st.session_state.workflow_status = "RUNNING"
                st.session_state.execution_result = None
                st.session_state.execution_screenshot = None
                st.session_state.product_results = None
                st.session_state.generated_excel = None
                clear_session_logs()
                status_placeholder = st.empty()

                def step_status_callback(step_num: int, state_name: str, detail_msg: str):
                    status_placeholder.info(f"⏳ **Step {step_num}/{len(wf.steps)}**: {detail_msg}")

                with st.spinner("Executing workflow across applications..."):
                    exec_res = execute_workflow_run(
                        workflow=wf,
                        user_id=user_id,
                        headless=headless,
                        timeout=timeout_val,
                        confirmed=st.session_state.get("workflow_confirmed", False),
                        status_callback=step_status_callback
                    )
                    st.session_state.execution_result = exec_res
                    st.session_state.execution_screenshot = exec_res.get("final_screenshot")
                    st.session_state.product_results = exec_res.get("products", [])
                    st.session_state.generated_excel = exec_res.get("excel_file")
                    if exec_res.get("requires_confirmation"):
                        st.session_state.workflow_status = "WAITING_CONFIRMATION"
                    else:
                        st.session_state.workflow_status = "COMPLETED" if exec_res["success"] else "FAILED"
                        st.session_state.workflow_confirmed = False
                    st.rerun()

    # Step 3: Execution Result Section (TASK, WORKFLOW, EXECUTION, VERIFICATION, FINAL RESULT)
    res = st.session_state.get("execution_result")
    if res:
        with st.container(border=True):
            st.markdown("### 3. Workflow Result")

            # --- A. TASK ---
            st.markdown("#### 🎯 Task")
            st.markdown(f"**Request:** `{st.session_state.get('current_prompt', 'Automated Workflow')}`")

            # Applications Used
            apps_used = res.get("applications", [])
            if apps_used:
                app_badges = " ".join([f"<span style='background:#1e3a8a;color:#93c5fd;padding:3px 8px;border-radius:8px;font-size:12px;margin-right:6px;'>{a}</span>" for a in apps_used])
                st.markdown(f"**Applications Utilized:** {app_badges}", unsafe_allow_html=True)
            st.write("")

            # --- B. WORKFLOW ---
            if wf and wf.steps:
                st.markdown("#### 📋 Workflow Plan")
                for s_idx, stp in enumerate(wf.steps, start=1):
                    st.markdown(f"{s_idx}. {stp.to_display_label()}")
                st.write("")

            # --- C. EXECUTION CHECKLIST ---
            exec_checklist = res.get("execution_checklist", [])
            if exec_checklist:
                st.markdown("#### ⚙️ Execution")
                for item in exec_checklist:
                    st.markdown(f"<span style='color: #6ee7b7;'>{item}</span>", unsafe_allow_html=True)
                st.write("")

            # --- D. VERIFICATION CHECKLIST ---
            verif_items = res.get("verification_items", [])
            if verif_items:
                st.markdown("#### 🛡️ Verification")
                for v_item in verif_items:
                    if v_item.startswith("✓"):
                        st.markdown(f"<span style='color: #6ee7b7; font-weight: 600;'>{v_item}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span style='color: #fca5a5; font-weight: 600;'>{v_item}</span>", unsafe_allow_html=True)
                st.write("")

            # --- E. EMAIL PREVIEWS & PER-RECIPIENT RESULTS ---
            email_context = res.get("context", {}) or {}
            email_results = res.get("email_results") or email_context.get("email_results") or []
            email_summary = res.get("email_summary") or email_context.get("email_summary") or {}
            reminders = email_context.get("reminders") or []
            email_messages = email_context.get("email_messages") or []
            if reminders or email_results or email_messages:
                st.markdown("#### 📧 Email Automation")
                sm1, sm2, sm3, sm4 = st.columns(4)
                sm1.metric("Prepared", email_summary.get("prepared", len(reminders)))
                sm2.metric("Submitted", email_summary.get("submitted", email_summary.get("sent", sum(1 for x in email_results if x.get("status") in ("SENT", "SIMULATED")))))
                sm3.metric("Failed", email_summary.get("failed", sum(1 for x in email_results if x.get("status") == "FAILED")))
                sm4.metric("Skipped / Pending", (email_summary.get("skipped", 0) + email_summary.get("pending_verification", 0)))
                provider_info = email_context.get("email_provider") or {}
                if provider_info:
                    label = "connected" if provider_info.get("connected") else "not connected"
                    st.caption(f"Provider: {provider_info.get('provider', 'unknown')} ({label}). Submission evidence is not delivery evidence.")

                for idx, preview in enumerate(reminders, 1):
                    recipient = preview.get("to") or "Missing recipient"
                    status = preview.get("status", "PREVIEW")
                    with st.expander(f"{idx}. {recipient} · {preview.get('subject', '(no subject)')} · {status}"):
                        st.markdown(f"**Attachment(s):** {', '.join(os.path.basename(str(a)) for a in preview.get('attachments', []) or ([preview.get('attachment')] if preview.get('attachment') else [])) or 'None'}")
                        if preview.get("validation_errors"):
                            st.error("; ".join(preview["validation_errors"]))
                        st.text_area("Email body", preview.get("body", ""), height=150, key=f"email_preview_body_{idx}", disabled=True)

                for idx, result in enumerate(email_results, 1):
                    status = result.get("status", "UNKNOWN")
                    recipient = result.get("to", "unknown recipient")
                    evidence = result.get("provider_message_id") or result.get("email_id") or result.get("error") or result.get("skip_reason") or "No evidence"
                    st.caption(f"{status}: {recipient} · {result.get('subject', '(no subject)')} · evidence: {evidence}")

                for message in email_messages:
                    with st.expander(f"Read: {message.get('subject') or '(no subject)'}"):
                        st.caption(f"From: {message.get('from', 'unknown')} · Received: {message.get('timestamp', message.get('date', 'unknown'))}")
                        st.text(message.get("body", ""))

            # --- E. PRODUCT SEARCH RESULTS TABLE & EXCEL (If Available) ---
            dash_products = res.get("products") or res.get("extracted_data", {}).get("products") or st.session_state.get("product_results") or []
            dash_excel = res.get("excel_file") or res.get("extracted_data", {}).get("excel_file") or st.session_state.get("generated_excel")

            if dash_products:
                st.markdown("#### 🛒 Product Search Results")
                st.markdown(f"**Found {len(dash_products)} authentic product listings:**")
                table_rows = []
                for idx, p in enumerate(dash_products, 1):
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

            if dash_excel and os.path.exists(dash_excel):
                st.markdown("#### 📊 Excel Report")
                f_name = os.path.basename(dash_excel)
                f_size = os.path.getsize(dash_excel)
                st.caption(f"✓ Excel report generated automatically ({f_name}, {f_size:,} bytes)")
                try:
                    with open(dash_excel, "rb") as f:
                        f_bytes = f.read()
                    st.download_button(
                        label="📥 Download Excel Report (.xlsx)",
                        data=f_bytes,
                        file_name=f_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Error loading Excel file: {e}")
                st.write("")

            # --- F. FINAL RESULT ---
            st.markdown("#### 🏁 Final Result")
            if res.get("status") == "WAITING_CONFIRMATION":
                st.warning(f"⏸️ **{res.get('summary')}**")
                c_btn1, c_btn2 = st.columns([2, 4])
                with c_btn1:
                    if st.button("Confirm & Send / Complete Order", type="primary"):
                        st.session_state.workflow_confirmed = True
                        # Run to complete
                        with st.spinner("Completing authorized actions..."):
                            final_run = execute_workflow_run(
                                workflow=wf,
                                user_id=user_id,
                                headless=False,
                                confirmed=True
                            )
                            st.session_state.execution_result = final_run
                            st.session_state.execution_screenshot = final_run.get("final_screenshot")
                            st.session_state.product_results = final_run.get("products", [])
                            st.session_state.generated_excel = final_run.get("excel_file")
                            st.session_state.workflow_status = "COMPLETED"
                            st.session_state.workflow_confirmed = False
                            st.rerun()
            elif res["success"]:
                st.success(f"✓ **{res.get('summary', 'Workflow executed and verified successfully.')}**")
            else:
                st.error(f"❌ **Execution Failed**: {res.get('error', 'Workflow encountered an error.')}")

            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Status", res.get("status", "SUCCESS"))
            m2.metric("Steps Completed", f"{res['completed_steps']} / {res['total_steps']}")
            m3.metric("Execution Time", f"{res['execution_time']}s")

            # Screenshots if any
            screenshots = res.get("screenshots", [])
            if screenshots:
                st.markdown("#### 📸 Captured Browser Screenshots")
                cols = st.columns(min(len(screenshots), 3))
                for idx, shot in enumerate(screenshots):
                    with cols[idx % len(cols)]:
                        if shot.startswith("data:image") or shot.startswith("http") or os.path.exists(shot):
                            st.image(shot, caption=f"Screenshot {idx+1}", use_container_width=True)
