"""
Selenium WebDriver Browser Automation Engine
Executes validated structured actions using explicit waits and robust locators.
"""

import os
import time
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    ElementNotInteractableException,
)

from workflows.actions import (
    ACTION_OPEN_URL,
    ACTION_TYPE,
    ACTION_CLICK,
    ACTION_SEARCH,
    ACTION_SELECT,
    ACTION_SCROLL,
    ACTION_WAIT,
    ACTION_GO_BACK,
    ACTION_GET_TEXT,
    ACTION_SCREENSHOT,
    ACTION_SEARCH_PRODUCT,
    ACTION_ADD_TO_CART,
    ACTION_REVIEW_ORDER,
    ACTION_DOWNLOAD_INVOICE,
    SEMANTIC_TARGET_SELECTORS,
)
from workflows.schemas import Workflow, WorkflowStep
from utils.logger import logger, add_log_entry
from utils.helpers import get_screenshot_dir, generate_id


class SeleniumEngine:
    """Encapsulates Selenium WebDriver session and step execution."""

    def __init__(self, headless: bool = False, timeout: int = 15):
        self.headless = headless
        self.timeout = timeout
        self.driver: Optional[webdriver.Chrome] = None
        self.screenshots: List[str] = []
        self.extracted_data: Dict[str, Any] = {}

    def start_driver(self) -> None:
        """Initializes Chrome WebDriver with optimized flags."""
        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--log-level=3")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(self.timeout)
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            add_log_entry(f"Selenium Chrome WebDriver initialized (Headless={self.headless}).", "INFO")
        except Exception as e:
            logger.error(f"Failed to start Selenium WebDriver: {e}")
            raise WebDriverException(f"Could not launch Chrome browser: {e}")

    def quit_driver(self) -> None:
        """Safely closes the browser session."""
        if self.driver:
            try:
                self.driver.quit()
                add_log_entry("Selenium browser session closed.")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None

    def capture_final_screenshot(self, status: str = "success") -> Optional[str]:
        """
        Captures a high-resolution screenshot of the final browser state.
        Ensures page rendering has settled and writes to screenshots/ with unique timestamp.
        """
        if not self.driver:
            return None
        try:
            # Allow final page repaints/DOM transitions to settle
            time.sleep(1.0)
            screenshot_dir = get_screenshot_dir()
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_suffix = generate_id("shot")
            prefix = "execution" if status == "success" else "failure"
            filename = f"{prefix}_{timestamp_str}_{unique_suffix}.png"
            filepath = os.path.join(screenshot_dir, filename)

            # Dismiss/accept any open JavaScript alert so it doesn't block screenshot
            try:
                alert = self.driver.switch_to.alert
                alert.accept()
            except Exception:
                pass

            self.driver.save_screenshot(filepath)
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                self.screenshots.append(filepath)
                log_tag = "Final execution screenshot captured" if status == "success" else "Failure screenshot captured"
                add_log_entry(f"[SCREENSHOT] {log_tag}: {filename}")
                return filepath
        except Exception as e:
            logger.warning(f"Failed to capture final screenshot: {e}")
        return None

    def find_element(self, target_str: str, timeout: Optional[int] = None):
        """
        Locates an element using explicit locator strategies:
        1. Check semantic target mappings (e.g. search_box, search_button)
        2. CSS Selector
        3. By ID
        4. By Name
        5. By XPath
        6. By visible button/link text or placeholder
        """
        if not self.driver:
            raise WebDriverException("WebDriver is not running.")

        wait_time = timeout or self.timeout
        wait = WebDriverWait(self.driver, min(wait_time, 4))
        target = (target_str or "").strip()
        t_lower = target.lower()

        # Strategy 0: Semantic Target Selectors FIRST for search, button, input aliases
        norm_keys = [
            t_lower,
            t_lower.replace("-", "_").replace(" ", "_"),
            t_lower.replace("_", "-").replace(" ", "-"),
            t_lower.replace(" ", "")
        ]
        semantic_candidates = []
        for k in norm_keys:
            if k in SEMANTIC_TARGET_SELECTORS:
                semantic_candidates.extend(SEMANTIC_TARGET_SELECTORS[k])

        if not semantic_candidates and ("search" in t_lower or "query" in t_lower):
            semantic_candidates.extend(SEMANTIC_TARGET_SELECTORS.get("search_box", []))

        for css in semantic_candidates:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, css)
                for el in found:
                    if el.is_displayed():
                        return el
            except Exception:
                continue

        # Strategy 1: Explicit CSS Selector (#id, .class, [attr], tag#id)
        if any(c in target for c in ["#", ".", "[", ">", ":"]):
            try:
                return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, target)))
            except Exception:
                pass

        # Strategy 2: Fast ID check (non-blocking)
        try:
            elems = self.driver.find_elements(By.ID, target)
            for el in elems:
                if el.is_displayed():
                    return el
            if elems:
                return elems[0]
        except Exception:
            pass

        # Strategy 3: Fast Name check (non-blocking)
        try:
            elems = self.driver.find_elements(By.NAME, target)
            for el in elems:
                if el.is_displayed():
                    return el
            if elems:
                return elems[0]
        except Exception:
            pass

        # Strategy 4: Explicit XPath
        if target.startswith("//") or target.startswith("("):
            try:
                return wait.until(EC.presence_of_element_located((By.XPATH, target)))
            except Exception:
                pass

        # Strategy 6: Heuristic Text or Placeholder Matching
        try:
            xpath_expr = (
                f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{target.lower()}')] | "
                f"//input[@type='submit' or @type='button'][contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{target.lower()}')] | "
                f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{target.lower()}')] | "
                f"//input[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{target.lower()}')] | "
                f"//textarea[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{target.lower()}')]"
            )
            elems = self.driver.find_elements(By.XPATH, xpath_expr)
            for el in elems:
                if el.is_displayed():
                    return el
        except Exception:
            pass

        raise NoSuchElementException(f"Could not locate element matching target '{target_str}'.")

    def execute_step(self, step: WorkflowStep) -> None:
        """Executes an individual atomic workflow step."""
        if not self.driver:
            raise WebDriverException("Browser is not active.")

        action = step.action.upper()
        target_str = step.get_target_string()
        value = step.value or ""

        if action == ACTION_OPEN_URL:
            url = step.url or value or target_str
            if not url:
                raise ValueError("OPEN_URL requires a valid 'url' property.")
            # Resolve relative local file paths to absolute file:// URLs
            if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                local_path = os.path.join(project_root, url.replace("/", os.sep))
                if os.path.exists(local_path):
                    url = f"file:///{local_path.replace(os.sep, '/')}"
                else:
                    url = f"https://{url}"

            add_log_entry(f"Navigating to URL: {url}")
            self.driver.get(url)
            time.sleep(1)

        elif action in (ACTION_TYPE, ACTION_SEARCH):
            try:
                elem = self.find_element(target_str)
            except NoSuchElementException:
                if action == ACTION_SEARCH or "search" in target_str.lower():
                    elem = self.find_element("search_box")
                else:
                    raise
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            try:
                elem.clear()
                elem.send_keys(value)
            except Exception:
                # Robust fallback: set value via JavaScript if element is hidden/read-only
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); "
                    "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                    elem, value
                )
            add_log_entry(f"Entered text '{value}' into target '{target_str}'.")

            if action == ACTION_SEARCH:
                try:
                    elem.send_keys(Keys.ENTER)
                except Exception:
                    self.driver.execute_script("if(arguments[0].form) { arguments[0].form.submit(); }", elem)
                add_log_entry(f"Submitted search form for '{target_str}'.")
                time.sleep(2)

        elif action == ACTION_CLICK:
            try:
                elem = self.find_element(target_str)
            except NoSuchElementException:
                t_clean = target_str.lower().strip()
                if t_clean in ("search_button", "search-button", "search button", "search_btn", "search-btn", "searchbtn"):
                    elem = self.find_element("search_button")
                elif t_clean in ("submit_button", "submit-button", "submit button", "submit_btn", "submit-btn", "submit"):
                    elem = self.find_element("submit_button")
                else:
                    raise
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            try:
                elem.click()
            except Exception:
                # Fallback to JavaScript click if blocked by overlay or not directly clickable
                self.driver.execute_script("arguments[0].click();", elem)
            add_log_entry(f"Clicked element '{target_str}'.")
            time.sleep(1)

        elif action == ACTION_SELECT:
            elem = self.find_element(target_str)
            try:
                select_obj = Select(elem)
                try:
                    select_obj.select_by_visible_text(value)
                except Exception:
                    select_obj.select_by_value(value)
                add_log_entry(f"Selected option '{value}' from dropdown '{target_str}'.")
            except Exception:
                # If not standard <select>, click matching text option
                elem.click()
                time.sleep(0.5)
                opt = self.find_element(value)
                opt.click()

        elif action == ACTION_SCROLL:
            direction = value.lower() if value else "down"
            pixels = 500 if direction != "up" else -500
            self.driver.execute_script(f"window.scrollBy(0, {pixels});")
            add_log_entry(f"Scrolled page {direction} by {abs(pixels)}px.")
            time.sleep(0.5)

        elif action == ACTION_WAIT:
            try:
                wait_sec = float(value) if value else 2.0
            except ValueError:
                wait_sec = 2.0
            add_log_entry(f"Pausing for {wait_sec} seconds...")
            time.sleep(wait_sec)

        elif action == ACTION_GO_BACK:
            self.driver.back()
            add_log_entry("Navigated back to previous page.")
            time.sleep(1)

        elif action == ACTION_GET_TEXT:
            elem = self.find_element(target_str)
            text_val = elem.text or elem.get_attribute("value") or ""
            self.extracted_data[target_str] = text_val
            add_log_entry(f"Extracted text from '{target_str}': {text_val[:50]}...")

        elif action == ACTION_SCREENSHOT:
            screenshot_dir = get_screenshot_dir()
            filename = f"screenshot_{generate_id('img')}.png"
            filepath = os.path.join(screenshot_dir, filename)
            self.driver.save_screenshot(filepath)
            self.screenshots.append(filepath)
            add_log_entry(f"Captured screenshot: {filename}")

        elif action == ACTION_SEARCH_PRODUCT:
            import urllib.parse
            query = value or target_str or "product"
            search_input = None
            candidates = [
                target_str,
                "input#twotabsearchtextbox",
                "#twotabsearchtextbox",
                "input[name='field-keywords']",
                "input[name='q']",
                "input[placeholder*='search' i]",
                "input[type='search']",
                "#search",
                "#proc-search-input"
            ] + SEMANTIC_TARGET_SELECTORS.get("search_box", [])

            for sel in candidates:
                if not sel:
                    continue
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        if el.is_displayed():
                            search_input = el
                            break
                    if search_input:
                        break
                except Exception:
                    continue

            typed = False
            if search_input:
                try:
                    search_input.clear()
                    search_input.send_keys(query)
                    search_input.send_keys(Keys.ENTER)
                    typed = True
                except Exception:
                    pass

            if not typed:
                # Direct navigation fallback to ensure seamless multi-step progression
                cur_url = (self.driver.current_url or "").lower()
                if "flipkart" in cur_url:
                    search_url = f"https://www.flipkart.com/search?q={urllib.parse.quote_plus(query)}"
                else:
                    search_url = f"https://www.amazon.in/s?k={urllib.parse.quote_plus(query)}"
                self.driver.get(search_url)

            time.sleep(2)
            add_log_entry(f"Searched products for '{query}' using Selenium.", "ACTION")

        elif action == ACTION_ADD_TO_CART:
            btn = None
            if target_str:
                try:
                    btn = self.find_element(target_str)
                except Exception:
                    pass
            if not btn:
                # Find first visible add to cart button
                for sel in [".add-to-cart-btn", "button[id^='add-btn']", "button:contains('Add to Cart')"]:
                    try:
                        candidates = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for c in candidates:
                            if c.is_displayed():
                                btn = c
                                break
                        if btn:
                            break
                    except Exception:
                        continue
            if not btn:
                raise NoSuchElementException(f"Add to cart button for '{target_str}' could not be located.")

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            try:
                btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", btn)
            add_log_entry(f"Added product to cart using Selenium.")
            time.sleep(1)

        elif action == ACTION_REVIEW_ORDER:
            btn = None
            for sel in ["#checkout-btn", "button#checkout-btn", "button[onclick*='openReviewOrder']"]:
                try:
                    b = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if b.is_displayed():
                        btn = b
                        break
                except Exception:
                    continue
            if not btn:
                btn = self.find_element(target_str or "checkout-btn")

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            try:
                btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", btn)
            add_log_entry("Opened order review and calculated cart totals using Selenium.")
            time.sleep(1)

        elif action == ACTION_DOWNLOAD_INVOICE:
            btn = None
            for sel in ["#downloadInvoiceBtn", "button.invoice-btn", "button#downloadInvoiceBtn"]:
                try:
                    b = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if b.is_displayed():
                        btn = b
                        break
                except Exception:
                    continue
            if btn:
                try:
                    btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", btn)
                add_log_entry("Triggered invoice download in browser using Selenium.")
                time.sleep(1)

        else:
            raise ValueError(f"Unsupported action '{action}'.")


def run_selenium_workflow(
    workflow: Workflow,
    headless: bool = False,
    timeout: int = 15,
    status_callback: Optional[Callable[[int, str, str], None]] = None
) -> Tuple[bool, int, Optional[str], List[str], Dict[str, Any]]:
    """
    Executes a complete workflow using SeleniumEngine.
    Returns: (success: bool, completed_steps: int, error_msg: Optional[str], screenshots: List[str], extracted_data: Dict)
    """
    engine = SeleniumEngine(headless=headless, timeout=timeout)
    completed_steps = 0
    total_steps = len(workflow.steps)

    try:
        engine.start_driver()

        for idx, step in enumerate(workflow.steps, start=1):
            step_desc = step.to_display_label()
            if status_callback:
                status_callback(idx, "RUNNING", f"Executing Step {idx}/{total_steps}: {step_desc}")

            engine.execute_step(step)
            completed_steps += 1

            if status_callback:
                status_callback(idx, "COMPLETED", f"Step {idx}/{total_steps} Completed: {step_desc}")

        # Final screenshot on completion
        try:
            screenshot_dir = get_screenshot_dir()
            final_img = os.path.join(screenshot_dir, f"final_{generate_id('img')}.png")
            if engine.driver:
                engine.driver.save_screenshot(final_img)
                engine.screenshots.append(final_img)
        except Exception:
            pass

        return True, completed_steps, None, engine.screenshots, engine.extracted_data

    except Exception as e:
        raw_err = str(e)
        clean_err = raw_err
        if "Message: " in clean_err:
            clean_err = clean_err.split("Message: ")[-1]
        if "; For documentation on this error" in clean_err:
            clean_err = clean_err.split("; For documentation on this error")[0]
        if "\n" in clean_err:
            clean_err = clean_err.split("\n")[0]
        clean_err = clean_err.strip().rstrip(";")

        failed_step_num = completed_steps + 1
        logger.error(f"Execution failed on step {failed_step_num}: {clean_err}")
        if status_callback:
            status_callback(failed_step_num, "FAILED", f"Step {failed_step_num} Failed: {clean_err}")
        return False, completed_steps, clean_err, engine.screenshots, engine.extracted_data

    finally:
        engine.quit_driver()
