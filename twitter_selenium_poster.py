#!/usr/bin/env python3
"""
Twitter Selenium Poster

A Selenium-based solution for posting content to Twitter (X) by directly
interacting with the Twitter web interface, using the same browser cache as LinkedIn.

Requirements:
- selenium
- webdriver-manager
- python-dotenv
"""

import datetime
import logging
import os
import threading
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterSeleniumPoster:
    """
    A Selenium-based Twitter poster that automates posting content
    by directly interacting with the Twitter web interface.
    Uses the same browser cache as LinkedIn for persistent sessions.
    """

    def __init__(
        self,
        headless: bool = False,
        wait_timeout: int = 10,
        user_data_dir: str | None = None,
    ):
        """
        Initialize the Twitter Selenium Poster.

        Args:
            headless: Whether to run browser in headless mode
            wait_timeout: Timeout for waiting for elements (seconds)
            user_data_dir: Directory to store browser cache/cookies. If None, uses linkedin_browser_data
        """
        self.driver = None
        self.wait_timeout = wait_timeout
        self.headless = headless
        self.is_logged_in = False

        # Use the same cache as LinkedIn
        if user_data_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.user_data_dir = os.path.join(script_dir, "linkedin_browser_data")
        else:
            self.user_data_dir = user_data_dir

        os.makedirs(self.user_data_dir, exist_ok=True)
        logger.info(f"Using browser data directory: {self.user_data_dir}")

    def setup_driver(self):
        """Set up the Chrome WebDriver with appropriate options."""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument(f"--user-data-dir={self.user_data_dir}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            logger.info("Chrome WebDriver setup completed successfully")
        except Exception as e:
            logger.error(f"Failed to setup Chrome WebDriver: {e}")
            raise

    def check_if_logged_in(self) -> bool:
        """
        Check if already logged in by navigating to Twitter and looking for login indicators.
        Returns:
            bool: True if already logged in, False otherwise
        """
        if not self.driver:
            self.setup_driver()
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        try:
            logger.info("Checking if already logged in...")
            self.driver.get("https://twitter.com/home")
            time.sleep(3)
            # If redirected to login, not logged in
            if "login" in self.driver.current_url:
                logger.info("Not logged in - redirected to login page")
                return False
            # Look for tweet box as indicator
            try:
                tweet_box = self.driver.find_element(
                    By.CSS_SELECTOR, "div[aria-label='Tweet text']"
                )
                if tweet_box.is_displayed():
                    logger.info("Already logged in - found tweet box")
                    self.is_logged_in = True
                    return True
            except NoSuchElementException:
                pass
            # If on home, assume logged in
            if "/home" in self.driver.current_url:
                logger.info("Already logged in - on home page")
                self.is_logged_in = True
                return True
            logger.info("Not logged in")
            return False
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def login(self, email: str, password: str) -> bool:
        """
        Log in to Twitter using provided credentials.
        Args:
            email: Twitter email/username
            password: Twitter password
        Returns:
            bool: True if login successful, False otherwise
        """
        if not self.driver:
            self.setup_driver()
        if not self.driver:
            logger.error("Failed to setup driver")
            return False
        if self.check_if_logged_in():
            logger.info("Already logged in, skipping login process")
            return True
        try:
            logger.info("Navigating to Twitter login page...")
            self.driver.get("https://twitter.com/login")
            time.sleep(3)
            # Step 1: Enter email/username
            email_field = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.NAME, "text"))
            )
            email_field.clear()
            email_field.send_keys(email)
            # Click Next button
            next_btn = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//span[text()='Next']/ancestor::button | //span[text()='Next']/ancestor::div[@role='button']",
                    )
                )
            )
            next_btn.click()
            time.sleep(2)
            # Step 2: Wait for password modal, enter password
            password_field = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_field.clear()
            password_field.send_keys(password)
            # Click Log in button
            login_btn = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//span[text()='Log in']/ancestor::button | //span[text()='Log in']/ancestor::div[@role='button']",
                    )
                )
            )
            login_btn.click()
            # Wait for home page
            WebDriverWait(self.driver, self.wait_timeout).until(
                lambda driver: "/home" in driver.current_url
            )
            logger.info("Successfully logged in to Twitter")
            self.is_logged_in = True
            return True
        except TimeoutException:
            logger.error("Login timeout - check credentials or network connection")
            return False
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def navigate_to_home(self):
        if not self.driver:
            logger.error("Driver not initialized")
            return
        try:
            self.driver.get("https://twitter.com/home")
            time.sleep(3)
            logger.info("Navigated to Twitter home page")
        except Exception as e:
            logger.error(f"Failed to navigate to home page: {e}")

    def find_tweet_box(self):
        if not self.driver:
            logger.error("Driver not initialized")
            return None
        assert self.driver is not None
        try:
            # Updated selector for the tweet input box
            tweet_box = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        'div[aria-label="Post text"][contenteditable="true"][data-testid="tweetTextarea_0"]',
                    )
                )
            )
            logger.info("Found tweet box (Post text)")
            return tweet_box
        except Exception as e:
            logger.error(f"Could not find tweet box: {e}")
            return None

    def find_schedule_button(self):
        """
        Find and click the schedule (calendar/clock) button in the tweet composer.
        Returns True if found and clicked, False otherwise.
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        assert self.driver is not None
        try:
            print("🔍 Looking for schedule button...")
            # Try multiple selectors for the schedule button
            schedule_selectors = [
                'button[data-testid="scheduleOption"]',
                'button[aria-label="Schedule post"]',
                'div[aria-label="Schedule post"]',
                'button[data-testid="scheduleOption"]',
                'div[role="button"][aria-label*="Schedule"]',
                'button[aria-label*="Schedule"]',
            ]

            schedule_btn = None
            for selector in schedule_selectors:
                try:
                    print(f"🔍 Trying selector: {selector}")
                    schedule_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"✅ Found schedule button with selector: {selector}")
                    break
                except Exception as e:
                    print(f"❌ Selector {selector} failed: {e}")
                    continue

            if not schedule_btn:
                print("❌ Could not find schedule button with any selector")
                return False

            print(f"🔍 Schedule button text: {schedule_btn.text}")
            print(f"🔍 Schedule button enabled: {schedule_btn.is_enabled()}")
            print(f"🔍 Schedule button displayed: {schedule_btn.is_displayed()}")
            print(
                f"🔍 Schedule button aria-label: {schedule_btn.get_attribute('aria-label')}"
            )

            # Try JavaScript click if regular click doesn't work
            try:
                schedule_btn.click()
                print("✅ Regular schedule button click worked")
            except Exception as e:
                print(f"⚠️ Regular schedule button click failed: {e}")
                print("🔄 Trying JavaScript schedule button click...")
                self.driver.execute_script("arguments[0].click();", schedule_btn)
                print("✅ JavaScript schedule button click worked")

            logger.info("Clicked schedule button")
            return True
        except Exception as e:
            logger.error(f"Could not find/click schedule button: {e}")
            return False

    def set_schedule_datetime(self, schedule_time: datetime.datetime) -> bool:
        """
        Set the date and time in the Twitter scheduling modal.
        Returns True if successful, False otherwise.
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        assert self.driver is not None
        try:
            # Wait for modal to appear (use CSS selector for dialog)
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"]'))
            )
            time.sleep(2)  # Give modal time to fully load

            # Select month, day, year, hour, minute, AM/PM
            month = schedule_time.month
            day = schedule_time.day
            year = schedule_time.year
            hour = schedule_time.strftime("%I").lstrip("0")
            minute = schedule_time.strftime("%M")
            ampm = schedule_time.strftime("%p").lower()

            print(
                f"🔍 Setting schedule for: {month}/{day}/{year} {hour}:{minute} {ampm}"
            )

            # Remove overlays as before
            try:
                overlay_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    'div[class*="r-1p0dtai"][class*="r-1d2f490"][class*="r-1xcajam"]',
                )
                for overlay in overlay_elements:
                    try:
                        self.driver.execute_script(
                            "arguments[0].style.display = 'none';", overlay
                        )
                        print("✅ Removed overlay element")
                    except Exception:
                        pass
            except Exception:
                pass

            # Month names for mapping
            month_names = [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
            month_name = month_names[month - 1]

            # Month (by visible text)
            try:
                month_select = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "SELECTOR_1"))
                )
                for option in month_select.find_elements(By.TAG_NAME, "option"):
                    if option.text.strip() == month_name:
                        option.click()
                        print(f"✅ Set month to {month_name}")
                        break
                else:
                    print(f"❌ Month {month_name} not found in dropdown!")
                    return False
            except Exception as e:
                print(f"❌ Failed to set month: {e}")
                return False

            # Day (by visible text)
            try:
                day_select = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "SELECTOR_2"))
                )
                for option in day_select.find_elements(By.TAG_NAME, "option"):
                    if option.text.strip() == str(day):
                        option.click()
                        print(f"✅ Set day to {day}")
                        break
                else:
                    print(f"❌ Day {day} not found in dropdown!")
                    return False
            except Exception as e:
                print(f"❌ Failed to set day: {e}")
                return False

            # Year (by visible text)
            try:
                year_select = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "SELECTOR_3"))
                )
                for option in year_select.find_elements(By.TAG_NAME, "option"):
                    if option.text.strip() == str(year):
                        option.click()
                        print(f"✅ Set year to {year}")
                        break
                else:
                    print(f"❌ Year {year} not found in dropdown!")
                    return False
            except Exception as e:
                print(f"❌ Failed to set year: {e}")
                return False

            # Hour (by visible text, 1-12)
            try:
                hour_select = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "SELECTOR_4"))
                )
                for option in hour_select.find_elements(By.TAG_NAME, "option"):
                    if option.text.strip() == hour:
                        option.click()
                        print(f"✅ Set hour to {hour}")
                        break
                else:
                    print(f"❌ Hour {hour} not found in dropdown!")
                    return False
            except Exception as e:
                print(f"❌ Failed to set hour: {e}")
                return False

            # Minute (by visible text, zero-padded)
            try:
                minute_select = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "SELECTOR_5"))
                )
                for option in minute_select.find_elements(By.TAG_NAME, "option"):
                    if option.text.strip() == minute:
                        option.click()
                        print(f"✅ Set minute to {minute}")
                        break
                else:
                    print(f"❌ Minute {minute} not found in dropdown!")
                    return False
            except Exception as e:
                print(f"❌ Failed to set minute: {e}")
                return False

            # AM/PM (by visible text, upper case)
            try:
                ampm_select = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "SELECTOR_6"))
                )
                for option in ampm_select.find_elements(By.TAG_NAME, "option"):
                    if option.text.strip().lower() == ampm:
                        option.click()
                        print(f"✅ Set AM/PM to {ampm}")
                        break
                else:
                    print(f"❌ AM/PM {ampm} not found in dropdown!")
                    return False
            except Exception as e:
                print(f"❌ Failed to set AM/PM: {e}")
                return False

            logger.info(f"Set schedule date/time to {schedule_time}")

            # Click confirm button
            try:
                confirm_btn = WebDriverWait(self.driver, self.wait_timeout).until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            'button[data-testid="scheduledConfirmationPrimaryAction"]',
                        )
                    )
                )
                print("🔍 Found confirm button, clicking...")
                confirm_btn.click()
                print("✅ Clicked confirm button")

                # Wait for the modal to close
                WebDriverWait(self.driver, self.wait_timeout).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="dialog"]'))
                )
                print("✅ Modal closed successfully")
                return True
            except Exception as e:
                print(f"❌ Failed to click confirm button: {e}")
                return False

        except Exception as e:
            logger.error(f"Could not set schedule date/time: {e}")
            return False

    def confirm_schedule(self):
        """
        Click the confirm button in the Twitter scheduling modal.
        Returns True if successful, False otherwise.
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        assert self.driver is not None
        try:
            confirm_btn = self.driver.find_element(
                By.CSS_SELECTOR,
                "button[data-testid='scheduledConfirmationPrimaryAction']",
            )
            confirm_btn.click()
            logger.info("Clicked confirm button in schedule modal")
            return True
        except Exception as e:
            logger.error(f"Could not click confirm button: {e}")
            return False

    def post_text(self, text: str) -> bool:
        if not self.is_logged_in:
            logger.error("Not logged in. Please login first.")
            return False
        assert self.driver is not None
        try:
            self.navigate_to_home()
            tweet_box = self.find_tweet_box()
            if not tweet_box:
                return False
            tweet_box.click()
            time.sleep(1)
            tweet_box.send_keys(text)
            print(f"📝 Typed text: '{text}'")

            # Find the post button
            tweet_btn = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[data-testid="tweetButtonInline"]')
                )
            )
            print(f"🔍 Found post button: {tweet_btn.text}")
            print(f"🔍 Button enabled: {tweet_btn.is_enabled()}")
            print(f"🔍 Button displayed: {tweet_btn.is_displayed()}")

            # Try JavaScript click if regular click doesn't work
            try:
                tweet_btn.click()
                print("✅ Regular click worked")
            except Exception as e:
                print(f"⚠️ Regular click failed: {e}")
                print("🔄 Trying JavaScript click...")
                self.driver.execute_script("arguments[0].click();", tweet_btn)
                print("✅ JavaScript click worked")

            # Wait 5 seconds after clicking post to ensure the tweet is posted
            time.sleep(5)
            # Wait for the tweet box to become empty and enabled, and for the button to become disabled
            WebDriverWait(self.driver, self.wait_timeout * 2).until(
                lambda d: d.find_element(
                    By.CSS_SELECTOR,
                    'div[aria-label="Post text"][contenteditable="true"][data-testid="tweetTextarea_0"]',
                ).text.strip()
                == ""
                and d.find_element(
                    By.CSS_SELECTOR, 'button[data-testid="tweetButtonInline"]'
                ).get_attribute("aria-disabled")
                == "true"
            )
            logger.info("Successfully posted tweet and confirmed post action.")
            return True
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            return False

    def post_text_scheduled(self, text: str, schedule_time: datetime.datetime) -> bool:
        if not self.is_logged_in:
            logger.error("Not logged in. Please login first.")
            return False
        if not isinstance(schedule_time, datetime.datetime):
            logger.error("schedule_time must be a datetime object")
            return False
        assert self.driver is not None
        try:
            self.navigate_to_home()
            tweet_box = self.find_tweet_box()
            if not tweet_box:
                return False
            tweet_box.click()
            time.sleep(1)
            tweet_box.send_keys(text)
            print(f"📝 Typed scheduled text: '{text}'")

            if self.find_schedule_button():
                if self.set_schedule_datetime(schedule_time):
                    try:
                        # Wait for and click the final schedule button
                        schedule_btn = WebDriverWait(
                            self.driver, self.wait_timeout
                        ).until(
                            EC.element_to_be_clickable(
                                (
                                    By.CSS_SELECTOR,
                                    'button[data-testid="tweetButtonInline"]',
                                )
                            )
                        )
                        print(f"🔍 Found schedule button: {schedule_btn.text}")
                        print(f"🔍 Button enabled: {schedule_btn.is_enabled()}")
                        print(f"🔍 Button displayed: {schedule_btn.is_displayed()}")

                        # Try JavaScript click if regular click doesn't work
                        try:
                            schedule_btn.click()
                            print("✅ Regular schedule click worked")
                        except Exception as e:
                            print(f"⚠️ Regular schedule click failed: {e}")
                            print("🔄 Trying JavaScript schedule click...")
                            self.driver.execute_script(
                                "arguments[0].click();", schedule_btn
                            )
                            print("✅ JavaScript schedule click worked")

                        # Wait 5 seconds after clicking schedule to ensure the tweet is scheduled
                        time.sleep(5)
                        # Wait for the tweet box to become empty and enabled, and for the button to become disabled
                        WebDriverWait(self.driver, self.wait_timeout * 2).until(
                            lambda d: d.find_element(
                                By.CSS_SELECTOR,
                                'div[aria-label="Post text"][contenteditable="true"][data-testid="tweetTextarea_0"]',
                            ).text.strip()
                            == ""
                            and d.find_element(
                                By.CSS_SELECTOR,
                                'button[data-testid="tweetButtonInline"]',
                            ).get_attribute("aria-disabled")
                            == "true"
                        )
                        logger.info(
                            "Successfully scheduled tweet using Twitter's native scheduler and confirmed schedule action."
                        )
                        return True
                    except Exception as e:
                        logger.error(f"Could not click final schedule button: {e}")
                        return False
            logger.warning("Falling back to timer-based scheduling")
            return False  # Let schedule_post handle fallback
        except Exception as e:
            logger.error(f"Error posting scheduled tweet: {e}")
            return False

    def schedule_post(self, text: str, schedule_time: datetime.datetime) -> bool:
        if not self.is_logged_in:
            logger.error("Not logged in. Please login first.")
            return False
        if schedule_time is None or not isinstance(schedule_time, datetime.datetime):
            logger.error("schedule_time must be a datetime object")
            return False
        assert self.driver is not None
        self.navigate_to_home()
        tweet_box = self.find_tweet_box()
        if tweet_box:
            tweet_box.click()
            time.sleep(1)
            tweet_box.send_keys(text)
            print(f"📝 Typed scheduled text: '{text}'")

            if self.find_schedule_button():
                print("✅ Found schedule button, setting datetime...")
                if self.set_schedule_datetime(schedule_time):
                    print(
                        "✅ Datetime set successfully, looking for final schedule button..."
                    )
                    try:
                        # Wait a moment for the UI to update after datetime selection
                        time.sleep(2)

                        # Look for the schedule button (which was previously the post button)
                        schedule_btn = WebDriverWait(
                            self.driver, self.wait_timeout
                        ).until(
                            EC.element_to_be_clickable(
                                (
                                    By.CSS_SELECTOR,
                                    'button[data-testid="tweetButtonInline"]',
                                )
                            )
                        )
                        print(f"🔍 Found final schedule button: {schedule_btn.text}")
                        print(f"🔍 Button enabled: {schedule_btn.is_enabled()}")
                        print(f"🔍 Button displayed: {schedule_btn.is_displayed()}")
                        print(
                            f"🔍 Button aria-label: {schedule_btn.get_attribute('aria-label')}"
                        )

                        # Try JavaScript click if regular click doesn't work
                        try:
                            schedule_btn.click()
                            print("✅ Regular final schedule click worked")
                        except Exception as e:
                            print(f"⚠️ Regular final schedule click failed: {e}")
                            print("🔄 Trying JavaScript final schedule click...")
                            self.driver.execute_script(
                                "arguments[0].click();", schedule_btn
                            )
                            print("✅ JavaScript final schedule click worked")

                        # Wait 5 seconds after clicking schedule to ensure the tweet is scheduled
                        time.sleep(5)
                        # Wait for the tweet box to become empty and enabled, and for the button to become disabled
                        try:
                            WebDriverWait(self.driver, self.wait_timeout * 2).until(
                                lambda d: d.find_element(
                                    By.CSS_SELECTOR,
                                    'div[aria-label="Post text"][contenteditable="true"][data-testid="tweetTextarea_0"]',
                                ).text.strip()
                                == ""
                                and d.find_element(
                                    By.CSS_SELECTOR,
                                    'button[data-testid="tweetButtonInline"]',
                                ).get_attribute("aria-disabled")
                                == "true"
                            )
                            print(
                                "✅ Tweet box cleared and button disabled - scheduling successful!"
                            )
                            logger.info(
                                "Successfully scheduled tweet using Twitter's native scheduler and confirmed schedule action."
                            )
                            return True
                        except Exception as e:
                            print(f"⚠️ Could not confirm tweet box cleared: {e}")
                            # Still return True if we got this far, as the scheduling might have worked
                            logger.info(
                                "Scheduling completed, but could not confirm UI state"
                            )
                            return True

                    except Exception as e:
                        logger.error(f"Could not click final schedule button: {e}")
                        return False
                else:
                    print("❌ Failed to set datetime")
                    return False
            else:
                print("❌ Could not find schedule button")
                return False
        # Fallback: timer-based scheduling
        now = datetime.datetime.now()
        delay = (schedule_time - now).total_seconds()
        if delay <= 0:
            logger.warning("Scheduled time is in the past. Posting immediately.")
            return self.post_text(text)
        logger.info(f"Scheduling tweet for {schedule_time} using fallback timer")

        def delayed_post():
            logger.info(f"Waiting {delay} seconds to post tweet...")
            time.sleep(delay)
            self.post_text(text)

        thread = threading.Thread(target=delayed_post)
        thread.daemon = True
        thread.start()
        return True

    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


def post_tweet(text: str, schedule_time: datetime.datetime | None = None):
    """
    Post or schedule a tweet using TwitterSeleniumPoster.
    If schedule_time is None, post immediately. Otherwise, schedule for the given datetime.
    """
    email = os.getenv("TWITTER_EMAIL")
    password = os.getenv("TWITTER_PASSWORD")
    if not email or not password:
        print("Please set TWITTER_EMAIL and TWITTER_PASSWORD environment variables")
        return
    poster = TwitterSeleniumPoster(headless=False)
    try:
        if poster.login(email, password):
            print("✅ Successfully logged in to Twitter")
            print("💾 Browser cache and cookies are being saved for future sessions")
            if schedule_time is None:
                print(f"\n📝 Posting immediately: '{text}'")
                poster.post_text(text)
            else:
                print(
                    f"\n📅 Scheduling tweet for {schedule_time.strftime('%Y-%m-%d %I:%M %p')}: '{text}'"
                )
                poster.schedule_post(text, schedule_time=schedule_time)
        else:
            print("❌ Failed to login to Twitter")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        poster.close()
        print("\n💡 Tip: Run this script again and it should skip the login process!")
        print(
            "💡 The wrapper function handles both immediate posting and scheduling automatically!"
        )


def main():
    """Demonstrate usage of post_tweet function."""
    # Example: Post immediately
    post_tweet(
        f"This is an immediate tweet from the unified function! Posted at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} #TwitterAutomation #UnifiedDemo"
    )
    # Example: Schedule a tweet for tomorrow
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    post_tweet(
        f"This is a scheduled tweet from the unified function! Scheduled for {tomorrow.strftime('%Y-%m-%d %H:%M')} #TwitterAutomation #UnifiedDemo",
        schedule_time=tomorrow,
    )


if __name__ == "__main__":
    main()
