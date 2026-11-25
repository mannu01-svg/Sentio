"""Selenium fixtures for Sentio's end-to-end UI tests.

Environment variables
  BASE_URL             dashboard URL (default http://localhost:5173)
  SELENIUM_REMOTE_URL  use a Selenium Grid / selenium/standalone-chrome container
                       instead of a local Chrome, e.g. http://localhost:4444/wd/hub
  E2E_EMAIL / E2E_PASSWORD   login used by the tests (default: seeded admin)
  CHROME_BIN / CHROMEDRIVER  explicit browser + driver paths (Jenkins uses
                       Debian's chromium + chromium-driver)
  HEADLESS             "0" to watch the browser (local Chrome only)
  E2E_SCREENSHOTS      folder for failure screenshots (default tests/e2e/screenshots)

The whole folder is skipped when BASE_URL is not reachable, so `pytest` on a
laptop without the stack running still passes.
"""
import os
import pathlib
import urllib.request

import pytest

BASE_URL = os.getenv("BASE_URL", "http://localhost:5173").rstrip("/")
REMOTE = os.getenv("SELENIUM_REMOTE_URL")
EMAIL = os.getenv("E2E_EMAIL", "admin@sentio.app")
PASSWORD = os.getenv("E2E_PASSWORD", "admin123")
SHOTS = pathlib.Path(os.getenv("E2E_SCREENSHOTS", pathlib.Path(__file__).parent / "screenshots"))


def _reachable(url):
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    selenium_missing = False
    try:
        import selenium  # noqa: F401
    except ImportError:
        selenium_missing = True
    reason = None
    if selenium_missing:
        reason = "selenium not installed (pip install selenium)"
    elif not REMOTE and not _reachable(BASE_URL + "/login"):
        reason = f"Sentio UI not reachable at {BASE_URL} - start the stack first"
    if reason:
        skip = pytest.mark.skip(reason=reason)
        for item in items:
            if "e2e" in str(item.fspath):
                item.add_marker(skip)


def _chrome_service(webdriver):
    """Pick a ChromeDriver: $CHROMEDRIVER, else chromedriver-py, else Selenium Manager (None)."""
    if os.getenv("CHROMEDRIVER"):
        return webdriver.ChromeService(executable_path=os.environ["CHROMEDRIVER"])
    try:  # pip install chromedriver-py gives a driver that matches Chrome
        from chromedriver_py import binary_path
        return webdriver.ChromeService(executable_path=binary_path)
    except ImportError:
        return None  # Selenium Manager downloads the right driver


@pytest.fixture(scope="session")
def driver():
    from selenium import webdriver

    opts = webdriver.ChromeOptions()
    if os.getenv("HEADLESS", "1") != "0" or REMOTE:
        opts.add_argument("--headless=new")
    for arg in ("--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,900", "--disable-gpu"):
        opts.add_argument(arg)

    if os.getenv("CHROME_BIN"):
        opts.binary_location = os.environ["CHROME_BIN"]

    if REMOTE:
        drv = webdriver.Remote(command_executor=REMOTE, options=opts)
    else:
        service = _chrome_service(webdriver)
        drv = webdriver.Chrome(options=opts, service=service) if service else webdriver.Chrome(options=opts)
    drv.implicitly_wait(0)
    yield drv
    drv.quit()


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def credentials():
    return EMAIL, PASSWORD


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed and "driver" in item.fixturenames:
        SHOTS.mkdir(parents=True, exist_ok=True)
        try:
            item.funcargs["driver"].save_screenshot(str(SHOTS / f"{item.name}.png"))
        except Exception:
            pass
