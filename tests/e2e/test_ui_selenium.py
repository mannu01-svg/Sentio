"""End-to-end UI tests for the Sentio dashboard (Selenium WebDriver).

Run against a running stack:
    startup\\windows\\start.bat            (or start.sh)
    pip install selenium chromedriver-py
    pytest tests/e2e -v

Tests run in file order and share one browser session (login once).
"""
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

WAIT = 20


def wait(driver, timeout=WAIT):
    return WebDriverWait(driver, timeout)


def heading(driver, text):
    return wait(driver).until(
        EC.visibility_of_element_located((By.XPATH, f"//h1[contains(normalize-space(.), '{text}')]"))
    )


def sign_in(driver, base_url, email, password):
    driver.get(base_url + "/login")
    email_box = wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type=email]")))
    email_box.clear()
    email_box.send_keys(email)
    pw = driver.find_element(By.CSS_SELECTOR, "input[type=password]")
    pw.clear()
    pw.send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()


def open_page(driver, base_url, path, credentials):
    """Go to a protected page, signing in first if the session has none (lets tests run alone with -k)."""
    driver.get(base_url + path)
    time.sleep(0.5)
    if "/login" in driver.current_url:
        sign_in(driver, base_url, *credentials)
        wait(driver).until(EC.url_contains("/dashboard"))
        driver.get(base_url + path)


# 1 ─ login page ----------------------------------------------------------------
def test_login_page_renders(driver, base_url):
    driver.get(base_url + "/login")
    wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type=email]")))
    assert driver.find_element(By.CSS_SELECTOR, "input[type=password]").is_displayed()
    button = driver.find_element(By.CSS_SELECTOR, "button[type=submit]")
    assert "sign in" in button.text.lower()


def test_protected_route_redirects_to_login(driver, base_url):
    driver.delete_all_cookies()
    driver.get(base_url + "/login")
    driver.execute_script("window.localStorage.clear()")
    driver.get(base_url + "/dashboard")
    wait(driver).until(EC.url_contains("/login"))


def test_wrong_password_shows_error(driver, base_url, credentials):
    sign_in(driver, base_url, credentials[0], "definitely-wrong-password")
    err = wait(driver).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".auth-error")))
    assert err.text.strip()
    assert "/login" in driver.current_url


# 2 ─ happy path ----------------------------------------------------------------
def test_admin_login_reaches_dashboard(driver, base_url, credentials):
    sign_in(driver, base_url, *credentials)
    wait(driver).until(EC.url_contains("/dashboard"))
    heading(driver, "Dashboard")
    wait(driver).until(EC.visibility_of_element_located(
        (By.XPATH, "//*[contains(normalize-space(text()), 'Comments processed')]")))


@pytest.mark.parametrize("label,path,title", [
    ("Live Feed", "/live", "Live Feed"),
    ("Analyze", "/analyze", "Analyze"),
    ("History", "/history", "History"),
    ("Trends", "/trends", "Trends"),
    ("Models", "/models", "Model Comparison"),
    ("Pipeline", "/pipeline", "Pipeline"),
    ("Sources", "/sources", "Sources"),
])
def test_sidebar_navigation(driver, label, path, title):
    link = wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, f"//aside//a[contains(@class,'side-link')][.//span[normalize-space(.)='{label}']]")))
    link.click()
    wait(driver).until(EC.url_contains(path))
    heading(driver, title)


def test_pipeline_shows_kafka_and_mongodb(driver, base_url, credentials):
    open_page(driver, base_url, "/pipeline", credentials)
    heading(driver, "Pipeline")
    body = wait(driver).until(lambda d: d.find_element(By.TAG_NAME, "body").text
                              if "MongoDB" in d.find_element(By.TAG_NAME, "body").text else False)
    assert "Kafka" in body
    assert "PostgreSQL" in body


def test_paste_analysis_streams_and_lands_in_history(driver, base_url, credentials):
    title = f"Selenium run {int(time.time())}"
    open_page(driver, base_url, "/analyze/instagram", credentials)
    heading(driver, "Analyze Instagram")
    driver.find_element(By.CSS_SELECTOR, "input.input[placeholder^='Title']").send_keys(title)
    driver.find_element(By.CSS_SELECTOR, "textarea").send_keys(
        "I absolutely love this product, best purchase ever!\n"
        "Terrible support, I want a refund.\n"
        "It arrived on Tuesday.")
    driver.find_element(By.XPATH, "//button[contains(., 'Analyze pasted comments')]").click()

    ok = wait(driver, 30).until(EC.visibility_of_element_located(
        (By.XPATH, "//span[contains(normalize-space(.), 'comments streaming through the pipeline')]")))
    assert ok.text.strip().startswith("3")

    driver.find_element(By.XPATH, "//button[contains(., 'Open the analysis page')]").click()
    wait(driver).until(EC.url_contains("/analyze/post/"))

    driver.get(base_url + "/history")
    heading(driver, "History")
    wait(driver).until(EC.visibility_of_element_located(
        (By.XPATH, f"//*[contains(normalize-space(text()), '{title}')]")))


def test_theme_toggle(driver, base_url, credentials):
    open_page(driver, base_url, "/dashboard", credentials)
    heading(driver, "Dashboard")
    toggle = driver.find_element(By.XPATH, "//aside//button[contains(., 'mode')]")
    before = toggle.text
    toggle.click()
    wait(driver).until(lambda d: d.find_element(By.XPATH, "//aside//button[contains(., 'mode')]").text != before)
    driver.find_element(By.XPATH, "//aside//button[contains(., 'mode')]").click()  # restore


# 3 ─ logout --------------------------------------------------------------------
def test_logout_returns_to_login(driver, base_url, credentials):
    open_page(driver, base_url, "/dashboard", credentials)
    heading(driver, "Dashboard")
    driver.find_element(By.CSS_SELECTOR, "button[title='Sign out']").click()
    wait(driver).until(EC.url_contains("/login"))
    driver.get(base_url + "/dashboard")
    wait(driver).until(EC.url_contains("/login"))
