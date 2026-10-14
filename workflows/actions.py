"""
Workflows - Supported Actions and Semantic Target Mappings
Supports both Selenium browser automation actions and enterprise cross-application actions.
"""

# Supported Browser Actions (Executed via Selenium WebDriver)
ACTION_OPEN_URL = "OPEN_URL"
ACTION_TYPE = "TYPE"
ACTION_CLICK = "CLICK"
ACTION_SEARCH = "SEARCH"
ACTION_SELECT = "SELECT"
ACTION_SCROLL = "SCROLL"
ACTION_WAIT = "WAIT"
ACTION_GO_BACK = "GO_BACK"
ACTION_GET_TEXT = "GET_TEXT"
ACTION_SCREENSHOT = "SCREENSHOT"

BROWSER_ACTIONS = {
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
}

# Supported Enterprise Cross-Application Actions
ACTION_READ_EXCEL = "READ_EXCEL"
ACTION_FIND_UNPAID_INVOICES = "FIND_UNPAID_INVOICES"
ACTION_EXTRACT_INVOICE = "EXTRACT_INVOICE"
ACTION_GENERATE_REMINDER = "GENERATE_REMINDER"
ACTION_SEND_EMAIL = "SEND_EMAIL"
ACTION_SEARCH_EMAIL = "SEARCH_EMAIL"
ACTION_READ_EMAIL = "READ_EMAIL"
ACTION_EXTRACT_EMAIL_INFO = "EXTRACT_EMAIL_INFO"
ACTION_COMPOSE_EMAIL = "COMPOSE_EMAIL"
ACTION_ATTACH_FILE = "ATTACH_FILE"
ACTION_RECORD_RESULT = "RECORD_RESULT"
ACTION_UPDATE_EXCEL = "UPDATE_EXCEL"
ACTION_SEARCH_PRODUCT = "SEARCH_PRODUCT"
ACTION_EXTRACT_PRODUCT_DATA = "EXTRACT_PRODUCT_DATA"
ACTION_VALIDATE_PRODUCTS = "VALIDATE_PRODUCTS"
ACTION_GENERATE_EXCEL = "GENERATE_EXCEL"
ACTION_ADD_TO_CART = "ADD_TO_CART"
ACTION_REVIEW_ORDER = "REVIEW_ORDER"
ACTION_DOWNLOAD_INVOICE = "DOWNLOAD_INVOICE"
ACTION_CHECK_CALENDAR = "CHECK_CALENDAR"
ACTION_CHECK_TASKS = "CHECK_TASKS"
ACTION_UPDATE_TASK = "UPDATE_TASK"
ACTION_GENERATE_BRIEF = "GENERATE_BRIEF"
ACTION_GENERATE_REPORT = "GENERATE_REPORT"
ACTION_VERIFY = "VERIFY"

CROSS_APP_ACTIONS = {
    ACTION_READ_EXCEL,
    ACTION_FIND_UNPAID_INVOICES,
    ACTION_EXTRACT_INVOICE,
    ACTION_GENERATE_REMINDER,
    ACTION_SEND_EMAIL,
    ACTION_SEARCH_EMAIL,
    ACTION_READ_EMAIL,
    ACTION_EXTRACT_EMAIL_INFO,
    ACTION_COMPOSE_EMAIL,
    ACTION_ATTACH_FILE,
    ACTION_RECORD_RESULT,
    ACTION_UPDATE_EXCEL,
    ACTION_SEARCH_PRODUCT,
    ACTION_EXTRACT_PRODUCT_DATA,
    ACTION_VALIDATE_PRODUCTS,
    ACTION_GENERATE_EXCEL,
    ACTION_ADD_TO_CART,
    ACTION_REVIEW_ORDER,
    ACTION_DOWNLOAD_INVOICE,
    ACTION_CHECK_CALENDAR,
    ACTION_CHECK_TASKS,
    ACTION_UPDATE_TASK,
    ACTION_GENERATE_BRIEF,
    ACTION_GENERATE_REPORT,
    ACTION_VERIFY,
}

SUPPORTED_ACTIONS = BROWSER_ACTIONS.union(CROSS_APP_ACTIONS).union({
    ACTION_SEARCH_PRODUCT,
    ACTION_EXTRACT_PRODUCT_DATA,
    ACTION_VALIDATE_PRODUCTS,
    ACTION_GENERATE_EXCEL,
})

# Predefined Semantic Target Mappings (Common search & form elements)
_SEARCH_BOX_SELECTORS = [
    "textarea[name='q']",
    "input[name='q']",
    "#searchInput",
    "input#searchInput",
    "input[name='search']",
    "input#twotabsearchtextbox",
    "input[name='field-keywords']",
    "input[type='search']",
    "#search",
    "#search-bar",
    "#search_bar",
    "input[placeholder*='search' i]",
    "textarea[placeholder*='search' i]",
    "input[aria-label*='search' i]",
    "textarea[aria-label*='search' i]",
    "#proc-search-input"
]

_SEARCH_BUTTON_SELECTORS = [
    "#searchButton",
    "button#searchButton",
    "input#nav-search-submit-button",
    "#nav-search-submit-text input",
    "input[type='submit'][name='btnK']",
    "button[type='submit']",
    "input[type='submit']",
    "button[aria-label*='search' i]",
    "button.search-btn",
    "#proc-search-btn"
]

SEMANTIC_TARGET_SELECTORS = {
    # Search Box patterns & aliases
    "search_box": _SEARCH_BOX_SELECTORS,
    "search-box": _SEARCH_BOX_SELECTORS,
    "search_bar": _SEARCH_BOX_SELECTORS,
    "search-bar": _SEARCH_BOX_SELECTORS,
    "search bar": _SEARCH_BOX_SELECTORS,
    "searchbox": _SEARCH_BOX_SELECTORS,
    "searchbar": _SEARCH_BOX_SELECTORS,
    "search_input": _SEARCH_BOX_SELECTORS,
    "search-input": _SEARCH_BOX_SELECTORS,
    "search input": _SEARCH_BOX_SELECTORS,
    "search_field": _SEARCH_BOX_SELECTORS,
    "search-field": _SEARCH_BOX_SELECTORS,
    "search": _SEARCH_BOX_SELECTORS,
    "query": _SEARCH_BOX_SELECTORS,
    "q": _SEARCH_BOX_SELECTORS,

    # Search Button patterns & aliases
    "search_button": _SEARCH_BUTTON_SELECTORS,
    "search-button": _SEARCH_BUTTON_SELECTORS,
    "search button": _SEARCH_BUTTON_SELECTORS,
    "search_btn": _SEARCH_BUTTON_SELECTORS,
    "search-btn": _SEARCH_BUTTON_SELECTORS,
    "searchbtn": _SEARCH_BUTTON_SELECTORS,

    # Price Filter / eCommerce filters
    "price_filter": [
        "#high-price",
        "#low-price",
        "input[name='high-price']",
        "input[name='low-price']",
        "input[placeholder*='Max' i]",
        "input[placeholder*='Min' i]",
        "input[aria-label*='Maximum' i]",
        "input[aria-label*='Minimum' i]"
    ],
    # Submit Button patterns
    "submit_button": [
        "#submit-btn",
        "button[type='submit']",
        "input[type='submit']",
        "#submit",
        "button:has-text('Submit')"
    ],
    # First search result link pattern
    "first_result": [
        "#search .g a",
        "div.g h3 a",
        "div.s-main-slot div[data-component-type='s-search-result'] h2 a",
        "div.mw-search-result-heading a",
        "a h3",
        "main h2 a",
        "article a"
    ]
}
