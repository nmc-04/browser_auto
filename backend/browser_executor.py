import os
import time
from typing import Callable, Optional, List, Dict, Any
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError

from backend.workflow_models import Workflow, WorkflowStep, WorkflowResult
from backend.logger import add_log_entry, logger

# Create screenshot directory in scratch / temp directory
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def locate_element(page: Page, field: str, selector: Optional[str] = None, timeout_ms: int = 5000):
    """
    Attempts to locate an element on the page using standard heuristics:
    1. Explicit selector (if provided or field looks like a CSS/XPath selector)
    2. By label text
    3. By placeholder
    4. By name attribute
    5. By ID attribute
    6. By inner text / button text / role
    """
    target = selector or field or ""

    # Strategy 1: Explicit CSS or XPath selector syntax
    if selector or target.startswith("#") or target.startswith(".") or target.startswith("//") or "[" in target:
        loc = page.locator(target)
        if loc.count() > 0:
            return loc.first

    # Strategy 2: By exact or partial label
    try:
        loc = page.get_by_label(target, exact=False)
        if loc.count() > 0:
            return loc.first
    except Exception:
        pass

    # Strategy 3: By placeholder
    try:
        loc = page.get_by_placeholder(target, exact=False)
        if loc.count() > 0:
            return loc.first
    except Exception:
        pass

    # Strategy 4: By Name attribute
    loc = page.locator(f'[name="{target}"], [name*="{target}" i]')
    if loc.count() > 0:
        return loc.first

    # Strategy 5: By ID attribute
    loc = page.locator(f'#{target}')
    if loc.count() > 0:
        return loc.first

    # Strategy 6: By Text content (useful for buttons, links, clickable items)
    try:
        loc = page.get_by_role("button", name=target, exact=False)
        if loc.count() > 0:
            return loc.first
    except Exception:
        pass

    try:
        loc = page.get_by_text(target, exact=False)
        if loc.count() > 0:
            return loc.first
    except Exception:
        pass

    # Fallback locator
    return page.locator(target)


def execute_workflow(
    workflow: Workflow,
    update_status_cb: Optional[Callable[[int, int, str, str], None]] = None,
    settings: Optional[Dict[str, Any]] = None
) -> WorkflowResult:
    """
    Executes a validated Workflow using Playwright.
    """
    if not settings:
        settings = {}

    headless = settings.get("headless", False)
    browser_name = settings.get("browser_type", "Chrome").lower()
    timeout_sec = float(settings.get("timeout", 30))
    timeout_ms = int(timeout_sec * 1000)
    save_screenshots = settings.get("screenshots", True)

    logs: List[str] = []
    captured_screenshots: List[str] = []
    total_steps = len(workflow.steps)

    add_log_entry(logs, "Browser automation session initiated.")

    if not workflow.steps:
        return WorkflowResult(
            success=False,
            completed_steps=0,
            total_steps=0,
            message="No steps provided in workflow.",
            error="Empty workflow steps",
            logs=logs
        )

    with sync_playwright() as p:
        # Select browser engine based on settings
        if "firefox" in browser_name:
            browser_type = p.firefox
        elif "edge" in browser_name:
            browser_type = p.chromium
        else:
            browser_type = p.chromium

        add_log_entry(logs, f"Starting browser ({settings.get('browser_type', 'Chrome')}, Headless={headless})...")

        try:
            browser: Browser = browser_type.launch(headless=headless)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page: Page = context.new_page()
            page.set_default_timeout(timeout_ms)
        except Exception as e:
            error_msg = f"Failed to launch browser: {e}"
            add_log_entry(logs, error_msg)
            return WorkflowResult(
                success=False,
                completed_steps=0,
                total_steps=total_steps,
                message=error_msg,
                error=error_msg,
                logs=logs
            )

        completed_count = 0
        try:
            for idx, step in enumerate(workflow.steps, start=1):
                action = step.action.lower()
                target_desc = step.field or step.url or step.selector or "Page"
                action_desc = action.capitalize()

                add_log_entry(logs, f"Executing Step {idx}/{total_steps}: {action_desc} on '{target_desc}'")

                if update_status_cb:
                    try:
                        update_status_cb(idx, total_steps, action_desc, target_desc)
                    except Exception:
                        pass

                # Action 1: OPEN
                if action == "open":
                    raw_url = step.url or step.value or ""
                    # Check if relative local file
                    if not raw_url.startswith("http://") and not raw_url.startswith("https://") and not raw_url.startswith("file://"):
                        local_path = os.path.abspath(raw_url)
                        if os.path.exists(local_path):
                            raw_url = f"file:///{local_path.replace('\\', '/')}"
                        else:
                            # Try looking inside project directory
                            proj_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), raw_url))
                            if os.path.exists(proj_path):
                                raw_url = f"file:///{proj_path.replace('\\', '/')}"
                            else:
                                raw_url = f"http://{raw_url}"

                    add_log_entry(logs, f"Opening URL: {raw_url}")
                    page.goto(raw_url, wait_until="domcontentloaded", timeout=timeout_ms)

                # Action 2: FILL
                elif action == "fill":
                    field_name = step.field or step.selector
                    val = step.value or ""
                    elem = locate_element(page, field_name, step.selector, timeout_ms=timeout_ms)

                    try:
                        elem.wait_for(state="visible", timeout=timeout_ms)
                        elem.fill(val)
                    except PlaywrightTimeoutError:
                        raise RuntimeError(f"Could not find or fill field: '{field_name}'")

                # Action 3: CLICK
                elif action == "click":
                    field_name = step.field or step.selector
                    elem = locate_element(page, field_name, step.selector, timeout_ms=timeout_ms)

                    try:
                        elem.wait_for(state="visible", timeout=timeout_ms)
                        elem.click()
                    except PlaywrightTimeoutError:
                        raise RuntimeError(f"Could not find or click element: '{field_name}'")

                # Action 4: SELECT
                elif action == "select":
                    field_name = step.field or step.selector
                    val = step.value or ""
                    elem = locate_element(page, field_name, step.selector, timeout_ms=timeout_ms)

                    try:
                        elem.wait_for(state="visible", timeout=timeout_ms)
                        # Try selecting by label, value, or index
                        try:
                            elem.select_option(label=val)
                        except Exception:
                            elem.select_option(value=val)
                    except Exception:
                        raise RuntimeError(f"Could not select '{val}' in dropdown: '{field_name}'")

                # Action 5: UPLOAD
                elif action == "upload":
                    field_name = step.field or step.selector
                    file_path = step.value or ""
                    if not os.path.isabs(file_path):
                        file_path = os.path.abspath(file_path)

                    elem = locate_element(page, field_name, step.selector, timeout_ms=timeout_ms)
                    try:
                        elem.wait_for(state="attached", timeout=timeout_ms)
                        elem.set_input_files(file_path)
                    except Exception:
                        raise RuntimeError(f"Could not upload file to field: '{field_name}'")

                # Action 6: WAIT
                elif action == "wait":
                    wait_seconds = float(step.value) if step.value else 1.0
                    add_log_entry(logs, f"Waiting for {wait_seconds} seconds...")
                    time.sleep(wait_seconds)

                # Action 7: SCREENSHOT
                elif action == "screenshot":
                    shot_path = os.path.join(SCREENSHOT_DIR, f"screenshot_step_{idx}_{int(time.time())}.png")
                    page.screenshot(path=shot_path)
                    captured_screenshots.append(shot_path)
                    add_log_entry(logs, f"Saved screenshot to {shot_path}")

                completed_count += 1
                time.sleep(0.3)

            # Auto screenshot at end of workflow if enabled
            if save_screenshots and not captured_screenshots:
                final_shot = os.path.join(SCREENSHOT_DIR, f"final_execution_{int(time.time())}.png")
                page.screenshot(path=final_shot)
                captured_screenshots.append(final_shot)

            add_log_entry(logs, "Task completed successfully.")
            browser.close()

            return WorkflowResult(
                success=True,
                completed_steps=completed_count,
                total_steps=total_steps,
                message="Task completed successfully.",
                logs=logs,
                screenshots=captured_screenshots
            )

        except Exception as err:
            err_msg = str(err)
            add_log_entry(logs, f"Browser execution error: {err_msg}")
            try:
                if save_screenshots:
                    err_shot = os.path.join(SCREENSHOT_DIR, f"error_step_{completed_count+1}_{int(time.time())}.png")
                    page.screenshot(path=err_shot)
                    captured_screenshots.append(err_shot)
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass

            return WorkflowResult(
                success=False,
                completed_steps=completed_count,
                total_steps=total_steps,
                message=f"Execution stopped at step {completed_count + 1}: {err_msg}",
                error=err_msg,
                logs=logs,
                screenshots=captured_screenshots
            )
