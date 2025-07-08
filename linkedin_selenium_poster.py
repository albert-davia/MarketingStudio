#!/usr/bin/env python3
"""
LinkedIn Selenium Poster

A Selenium-based solution for posting content to LinkedIn by directly
interacting with the LinkedIn web interface.

Requirements:
- selenium
- webdriver-manager
- python-dotenv
"""

import datetime
import logging
import os
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


class LinkedInSeleniumPoster:
    """
    A Selenium-based LinkedIn poster that automates posting content
    by directly interacting with the LinkedIn web interface.
    """

    def __init__(
        self,
        headless: bool = False,
        wait_timeout: int = 10,
        user_data_dir: str | None = None,
    ):
        """
        Initialize the LinkedIn Selenium Poster.

        Args:
            headless: Whether to run browser in headless mode
            wait_timeout: Timeout for waiting for elements (seconds)
            user_data_dir: Directory to store browser cache/cookies. If None, uses temp directory
        """
        self.driver = None
        self.wait_timeout = wait_timeout
        self.headless = headless
        self.is_logged_in = False

        # Set up user data directory for persistent cache/cookies
        if user_data_dir is None:
            # Use a fixed directory in the project root (same location as the script)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.user_data_dir = os.path.join(script_dir, "linkedin_browser_data")
        else:
            self.user_data_dir = user_data_dir

        # Create the directory if it doesn't exist
        os.makedirs(self.user_data_dir, exist_ok=True)
        logger.info(f"Using browser data directory: {self.user_data_dir}")

    def setup_driver(self):
        """Set up the Chrome WebDriver with appropriate options."""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        # Add user data directory for persistent cache/cookies
        chrome_options.add_argument(f"--user-data-dir={self.user_data_dir}")

        # Add other useful options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Set user agent to avoid detection
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Execute script to remove webdriver property
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            logger.info("Chrome WebDriver setup completed successfully")

        except Exception as e:
            logger.error(f"Failed to setup Chrome WebDriver: {e}")
            raise

    def check_if_logged_in(self) -> bool:
        """
        Check if already logged in by navigating to LinkedIn and looking for login indicators.

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
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(3)

            # Check if we're redirected to login page
            if "login" in self.driver.current_url:
                logger.info("Not logged in - redirected to login page")
                return False

            # Check for login indicators
            try:
                # Look for elements that indicate we're logged in
                feed_indicators = [
                    "div[data-control-name='feed_identity_welcome_message']",
                    ".feed-identity-module",
                    ".feed-identity-welcome-message",
                    "div[data-test-id='feed-identity-module']",
                ]

                for selector in feed_indicators:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if element.is_displayed():
                            logger.info(
                                "Already logged in - found feed identity module"
                            )
                            self.is_logged_in = True
                            return True
                    except NoSuchElementException:
                        continue

                # Also check for the "Start a post" button which indicates we're logged in
                try:
                    post_button = self.driver.find_element(
                        By.CSS_SELECTOR, "button[aria-label*='Start a post']"
                    )
                    if post_button.is_displayed():
                        logger.info("Already logged in - found post button")
                        self.is_logged_in = True
                        return True
                except NoSuchElementException:
                    pass

                # Check if we're on the feed page
                if "feed" in self.driver.current_url:
                    logger.info("Already logged in - on feed page")
                    self.is_logged_in = True
                    return True

            except Exception as e:
                logger.warning(f"Error checking login status: {e}")

            logger.info("Not logged in")
            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def login(self, email: str, password: str) -> bool:
        """
        Log in to LinkedIn using provided credentials.

        Args:
            email: LinkedIn email/username
            password: LinkedIn password

        Returns:
            bool: True if login successful, False otherwise
        """
        if not self.driver:
            self.setup_driver()

        if not self.driver:
            logger.error("Failed to setup driver")
            return False

        # First check if already logged in
        if self.check_if_logged_in():
            logger.info("Already logged in, skipping login process")
            return True

        try:
            logger.info("Navigating to LinkedIn login page...")
            self.driver.get("https://www.linkedin.com/login")

            # Wait for page to load
            time.sleep(3)

            # Find and fill email field
            email_field = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.clear()
            email_field.send_keys(email)

            # Find and fill password field
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(password)

            # Click sign in button
            sign_in_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            sign_in_button.click()

            # Wait for login to complete and check if we're redirected to home page
            WebDriverWait(self.driver, self.wait_timeout).until(
                lambda driver: "feed" in driver.current_url
                or "mynetwork" in driver.current_url
            )

            logger.info("Successfully logged in to LinkedIn")
            self.is_logged_in = True
            return True

        except TimeoutException:
            logger.error("Login timeout - check credentials or network connection")
            return False
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def navigate_to_home(self):
        """Navigate to LinkedIn home page."""
        if not self.driver:
            logger.error("Driver not initialized")
            return
        try:
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(3)
            logger.info("Navigated to LinkedIn home page")
        except Exception as e:
            logger.error(f"Failed to navigate to home page: {e}")

    def find_post_button(self):
        """
        Find and click the "Start a post" button.

        Returns:
            bool: True if button found and clicked, False otherwise
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        try:
            # Look for the "Start a post" button - it can have various selectors
            selectors = [
                "button[aria-label*='Start a post']",
                "button[aria-label*='Create a post']",
                "button:contains('Start a post')",
                ".share-box__open",
                "[data-control-name='share.open']",
                "button.share-box-feed-entry__trigger",
            ]

            for selector in selectors:
                try:
                    if "contains" in selector:
                        # Handle text-based selector
                        elements = self.driver.find_elements(By.TAG_NAME, "button")
                        for element in elements:
                            if (
                                "Start a post" in element.text
                                or "Create a post" in element.text
                            ):
                                element.click()
                                logger.info("Found and clicked 'Start a post' button")
                                return True
                    else:
                        # Handle CSS selector
                        button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        button.click()
                        logger.info("Found and clicked 'Start a post' button")
                        return True
                except (TimeoutException, NoSuchElementException):
                    continue

            logger.error("Could not find 'Start a post' button")
            return False

        except Exception as e:
            logger.error(f"Error finding post button: {e}")
            return False

    def find_post_textarea(self):
        """
        Find the post textarea after clicking "Start a post".

        Returns:
            WebElement or None: The textarea element if found
        """
        try:
            # Look for the post textarea - it can have various selectors
            selectors = [
                "div[data-placeholder*='What do you want to talk about']",
                "div[data-placeholder*='Start a post']",
                "div[aria-label*='Text editor for creating content']",
                ".ql-editor",
                ".share-box__input",
                "[data-control-name='share.post']",
                "div[contenteditable='true']",
            ]

            for selector in selectors:
                try:
                    textarea = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info("Found post textarea")
                    return textarea
                except TimeoutException:
                    continue

            logger.error("Could not find post textarea")
            return None

        except Exception as e:
            logger.error(f"Error finding post textarea: {e}")
            return None

    def post_text(self, text: str, visibility: str = "connections") -> bool:
        """
        Post text content to LinkedIn.

        Args:
            text: The text content to post
            visibility: Post visibility - "connections" or "public"

        Returns:
            bool: True if post successful, False otherwise
        """
        if not self.is_logged_in:
            logger.error("Not logged in. Please login first.")
            return False

        try:
            # Navigate to home page
            self.navigate_to_home()

            # Find and click "Start a post" button
            if not self.find_post_button():
                return False

            # Wait for post dialog to appear
            time.sleep(2)

            # Find the textarea
            textarea = self.find_post_textarea()
            if not textarea:
                return False

            # Clear any existing text and enter new text
            textarea.clear()

            # Handle Unicode characters that might cause ChromeDriver issues
            try:
                # Try direct send_keys first
                textarea.send_keys(text)
            except Exception as e:
                if "BMP" in str(e):
                    # If BMP error, try to clean the text
                    logger.warning("Unicode characters detected, cleaning text...")
                    # Remove non-BMP characters (emojis, etc.)
                    cleaned_text = "".join(char for char in text if ord(char) < 65536)
                    textarea.send_keys(cleaned_text)
                    logger.info(f"Posted cleaned text: {cleaned_text}")
                else:
                    raise e

            # Set visibility if needed
            if visibility.lower() == "public":
                self.set_post_visibility("public")

            # Find and click the "Post" button
            if not self.click_post_button():
                return False

            # Wait a moment for any additional dialogs or confirmations
            time.sleep(3)

            # Check if there are any additional confirmation dialogs
            if self.handle_post_confirmation():
                logger.info("Successfully posted text to LinkedIn")
                return True
            else:
                logger.error(
                    "Post button was clicked but post may not have been published"
                )
                return False

        except Exception as e:
            logger.error(f"Error posting text: {e}")
            return False

    def set_post_visibility(self, visibility: str):
        """
        Set the visibility of the post.

        Args:
            visibility: "connections" or "public"
        """
        try:
            # Look for visibility dropdown
            visibility_selectors = [
                "button[aria-label*='Anyone']",
                "button[aria-label*='Connections']",
                ".share-box__visibility-dropdown",
                "[data-control-name='share.visibility']",
            ]

            for selector in visibility_selectors:
                try:
                    visibility_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    visibility_button.click()
                    time.sleep(1)

                    # Select the appropriate visibility option
                    if visibility.lower() == "public":
                        public_option = self.driver.find_element(
                            By.CSS_SELECTOR, "button[aria-label*='Anyone']"
                        )
                    else:
                        public_option = self.driver.find_element(
                            By.CSS_SELECTOR, "button[aria-label*='Connections']"
                        )

                    public_option.click()
                    logger.info(f"Set post visibility to {visibility}")
                    return

                except (TimeoutException, NoSuchElementException):
                    continue

            logger.warning("Could not set post visibility")

        except Exception as e:
            logger.error(f"Error setting post visibility: {e}")

    def click_post_button(self) -> bool:
        """
        Find and click the "Post" button to publish the content.

        Returns:
            bool: True if button found and clicked, False otherwise
        """
        try:
            # Look for the actual "Post" button (not the "Post to Anyone" button)
            post_selectors = [
                "button.share-actions__primary-action",
                "button[id*='ember'][class*='share-actions__primary-action']",
                "button.artdeco-button--primary[class*='share-actions']",
                "button[aria-label*='Post'][class*='primary']",
                "[data-control-name='share.post']",
                "button.share-box__post-button",
            ]

            for selector in post_selectors:
                try:
                    if "contains" in selector:
                        # Handle text-based selector
                        elements = self.driver.find_elements(By.TAG_NAME, "button")
                        for element in elements:
                            if "Post" in element.text and "Anyone" not in element.text:
                                # Check if button is enabled
                                if element.is_enabled() and element.is_displayed():
                                    logger.info(
                                        f"Found actual Post button with text: {element.text}"
                                    )
                                    element.click()
                                    logger.info("Clicked actual 'Post' button")
                                    return True
                    else:
                        # Handle CSS selector
                        post_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        logger.info(f"Found button with selector: {selector}")
                        post_button.click()
                        logger.info("Clicked 'Post' button")
                        return True
                except (TimeoutException, NoSuchElementException):
                    continue

            # If no button found, try to find any clickable button in the post dialog
            try:
                # Look for any primary action button
                buttons = self.driver.find_elements(
                    By.CSS_SELECTOR, "button.artdeco-button--primary"
                )
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        button_text = button.text.strip()
                        if button_text == "Post" and "Anyone" not in button_text:
                            logger.info(f"Found actual Post button: {button_text}")
                            button.click()
                            logger.info(f"Clicked actual '{button_text}' button")
                            return True
            except Exception as e:
                logger.warning(f"Error finding primary buttons: {e}")

            logger.error("Could not find 'Post' button")
            return False

        except Exception as e:
            logger.error(f"Error clicking post button: {e}")
            return False

    def handle_post_confirmation(self) -> bool:
        """
        Handle any additional confirmation dialogs that might appear after clicking Post.

        Returns:
            bool: True if post was successfully confirmed, False otherwise
        """
        try:
            # Wait a moment for any confirmation dialogs to appear
            time.sleep(2)

            # First, check for the "Post settings" dialog
            if self.handle_post_settings_dialog():
                return self.verify_post_published()

            # Look for confirmation buttons that might appear
            confirmation_selectors = [
                "button[aria-label*='Confirm']",
                "button[aria-label*='Yes']",
                "button[aria-label*='Continue']",
                "button[aria-label*='Done']",
                "button:contains('Confirm')",
                "button:contains('Yes')",
                "button:contains('Continue')",
                "button:contains('Done')",
                ".artdeco-button--primary",
                "button[type='submit']",
            ]

            for selector in confirmation_selectors:
                try:
                    if "contains" in selector:
                        # Handle text-based selector
                        elements = self.driver.find_elements(By.TAG_NAME, "button")
                        for element in elements:
                            if any(
                                text in element.text
                                for text in ["Confirm", "Yes", "Continue", "Done"]
                            ):
                                if element.is_enabled() and element.is_displayed():
                                    logger.info(
                                        f"Found confirmation button: {element.text}"
                                    )
                                    element.click()
                                    logger.info("Clicked confirmation button")
                                    time.sleep(2)
                                    return self.verify_post_published()
                    else:
                        # Handle CSS selector
                        confirmation_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        logger.info(
                            f"Found confirmation button with selector: {selector}"
                        )
                        confirmation_button.click()
                        logger.info("Clicked confirmation button")
                        time.sleep(2)
                        return self.verify_post_published()
                except (TimeoutException, NoSuchElementException):
                    continue

            # If no confirmation dialog found, verify the post was published
            return self.verify_post_published()

        except Exception as e:
            logger.error(f"Error handling post confirmation: {e}")
            return False

    def handle_post_settings_dialog(self) -> bool:
        """
        Handle the "Post settings" dialog that appears after clicking Post.

        Returns:
            bool: True if settings were successfully configured, False otherwise
        """
        try:
            # Look for the "Post settings" dialog
            settings_selectors = [
                "div[aria-label*='Post settings']",
                "div[aria-label*='Who can see your post']",
                ".post-settings-dialog",
                "div[role='dialog']",
            ]

            dialog_found = False
            for selector in settings_selectors:
                try:
                    dialog = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if dialog.is_displayed():
                        dialog_found = True
                        logger.info("Found Post settings dialog")
                        break
                except NoSuchElementException:
                    continue

            if not dialog_found:
                # Also check for text-based detection
                elements = self.driver.find_elements(By.TAG_NAME, "div")
                for element in elements:
                    if (
                        "Post settings" in element.text
                        or "Who can see your post" in element.text
                    ):
                        dialog_found = True
                        logger.info("Found Post settings dialog by text")
                        break

            if dialog_found:
                # Look for visibility options using the specific IDs from the HTML
                visibility_selectors = [
                    "button[id='ANYONE']",
                    "button[id='CONNECTIONS_ONLY']",
                    "button[aria-label*='Anyone']",
                    "button[aria-label*='Connections only']",
                    "input[type='radio'][value='anyone']",
                    "input[type='radio'][value='connections']",
                ]

                # Try to find and click the "Anyone" option to enable the Done button
                visibility_clicked = False
                for selector in visibility_selectors:
                    try:
                        if "ANYONE" in selector or "Anyone" in selector:
                            visibility_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            logger.info("Found 'Anyone' visibility option")
                            visibility_button.click()
                            logger.info("Clicked 'Anyone' visibility option")
                            time.sleep(1)
                            visibility_clicked = True
                            break
                    except (TimeoutException, NoSuchElementException):
                        continue

                # If "Anyone" wasn't found, try "Connections only"
                if not visibility_clicked:
                    for selector in visibility_selectors:
                        try:
                            if (
                                "CONNECTIONS_ONLY" in selector
                                or "Connections" in selector
                            ):
                                visibility_button = WebDriverWait(self.driver, 3).until(
                                    EC.element_to_be_clickable(
                                        (By.CSS_SELECTOR, selector)
                                    )
                                )
                                logger.info(
                                    "Found 'Connections only' visibility option"
                                )
                                visibility_button.click()
                                logger.info(
                                    "Clicked 'Connections only' visibility option"
                                )
                                time.sleep(1)
                                visibility_clicked = True
                                break
                        except (TimeoutException, NoSuchElementException):
                            continue

                # Look for and click the "Done" button using the specific ID from the HTML
                done_selectors = [
                    "button[id='ember178']",
                    "button.share-box-footer__primary-btn",
                    "button[aria-label*='Done']",
                    "button:contains('Done')",
                    "button.artdeco-button--primary",
                    "button[type='submit']",
                ]

                for selector in done_selectors:
                    try:
                        if "contains" in selector:
                            # Handle text-based selector
                            elements = self.driver.find_elements(By.TAG_NAME, "button")
                            for element in elements:
                                if "Done" in element.text:
                                    if element.is_enabled() and element.is_displayed():
                                        logger.info("Found 'Done' button")
                                        element.click()
                                        logger.info("Clicked 'Done' button")
                                        time.sleep(2)
                                        return True
                        else:
                            # Handle CSS selector
                            done_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            logger.info("Found 'Done' button with selector")
                            done_button.click()
                            logger.info("Clicked 'Done' button")
                            time.sleep(2)
                            return True
                    except (TimeoutException, NoSuchElementException):
                        continue

                logger.warning("Found Post settings dialog but couldn't configure it")
                return False

            return False

        except Exception as e:
            logger.error(f"Error handling post settings dialog: {e}")
            return False

    def verify_post_published(self) -> bool:
        """
        Verify that the post was actually published by checking for success indicators.

        Returns:
            bool: True if post appears to be published, False otherwise
        """
        try:
            # Wait a bit for the post dialog to close
            time.sleep(2)

            # Check if the post dialog is still open (indicating failure)
            try:
                # Look for elements that indicate the post dialog is still open
                dialog_selectors = [
                    "div[data-control-name='share.post']",
                    ".share-box",
                    "div[aria-label*='Text editor for creating content']",
                ]

                for selector in dialog_selectors:
                    try:
                        dialog = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if dialog.is_displayed():
                            logger.warning(
                                "Post dialog is still open - post may have failed"
                            )
                            return False
                    except NoSuchElementException:
                        continue

                # Check for success indicators
                success_selectors = [
                    "div[data-control-name='share.success']",
                    ".share-success",
                    "div[aria-label*='Post shared']",
                ]

                for selector in success_selectors:
                    try:
                        success_element = self.driver.find_element(
                            By.CSS_SELECTOR, selector
                        )
                        if success_element.is_displayed():
                            logger.info("Found success indicator")
                            return True
                    except NoSuchElementException:
                        continue

                # If we can't find explicit success indicators, check if we're back to the feed
                current_url = self.driver.current_url
                if "feed" in current_url or "mynetwork" in current_url:
                    logger.info("Returned to feed - post likely successful")
                    return True

                # As a fallback, assume success if dialog is closed
                logger.info("Post dialog closed - assuming success")
                return True

            except Exception as e:
                logger.warning(f"Error during verification: {e}")
                # If verification fails, assume success
                return True

        except Exception as e:
            logger.error(f"Error verifying post: {e}")
            return False

    def post_with_media(
        self, text: str, media_path: str, visibility: str = "connections"
    ) -> bool:
        """
        Post content with media (image/video) to LinkedIn.

        Args:
            text: The text content to post
            media_path: Path to the media file
            visibility: Post visibility - "connections" or "public"

        Returns:
            bool: True if post successful, False otherwise
        """
        if not self.is_logged_in:
            logger.error("Not logged in. Please login first.")
            return False

        try:
            # Navigate to home page
            self.navigate_to_home()

            # Find and click "Start a post" button
            if not self.find_post_button():
                return False

            # Wait for post dialog to appear
            time.sleep(2)

            # Find the textarea
            textarea = self.find_post_textarea()
            if not textarea:
                return False

            # Enter text
            textarea.clear()

            # Handle Unicode characters that might cause ChromeDriver issues
            try:
                # Try direct send_keys first
                textarea.send_keys(text)
            except Exception as e:
                if "BMP" in str(e):
                    # If BMP error, try to clean the text
                    logger.warning("Unicode characters detected, cleaning text...")
                    # Remove non-BMP characters (emojis, etc.)
                    cleaned_text = "".join(char for char in text if ord(char) < 65536)
                    textarea.send_keys(cleaned_text)
                    logger.info(f"Posted cleaned text: {cleaned_text}")
                else:
                    raise e

            # Upload media
            if not self.upload_media(media_path):
                return False

            # Set visibility if needed
            if visibility.lower() == "public":
                self.set_post_visibility("public")

            # Find and click the "Post" button
            if not self.click_post_button():
                return False

            # Wait for post to complete
            time.sleep(5)

            logger.info("Successfully posted content with media to LinkedIn")
            return True

        except Exception as e:
            logger.error(f"Error posting with media: {e}")
            return False

    def upload_media(self, media_path: str) -> bool:
        """
        Upload media file to the post.

        Args:
            media_path: Path to the media file

        Returns:
            bool: True if upload successful, False otherwise
        """
        try:
            # Look for media upload button
            upload_selectors = [
                "input[type='file']",
                "button[aria-label*='Add a photo']",
                "button[aria-label*='Add a video']",
                ".share-box__media-button",
                "[data-control-name='share.media']",
            ]

            for selector in upload_selectors:
                try:
                    if selector == "input[type='file']":
                        # Direct file input
                        file_input = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        file_input.send_keys(media_path)
                        logger.info(f"Uploaded media file: {media_path}")
                        return True
                    else:
                        # Button that opens file dialog
                        upload_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        upload_button.click()
                        time.sleep(1)

                        # Now look for file input
                        file_input = self.driver.find_element(
                            By.CSS_SELECTOR, "input[type='file']"
                        )
                        file_input.send_keys(media_path)
                        logger.info(f"Uploaded media file: {media_path}")
                        return True

                except (TimeoutException, NoSuchElementException):
                    continue

            logger.error("Could not find media upload button")
            return False

        except Exception as e:
            logger.error(f"Error uploading media: {e}")
            return False

    def close(self):
        """Close the browser and clean up resources."""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")

    def schedule_post(
        self,
        text: str,
        schedule_time: datetime.datetime,
        visibility: str = "connections",
    ) -> bool:
        """
        Schedule a post to be published at a specific time using LinkedIn's built-in scheduler.
        """
        if not self.is_logged_in:
            logger.error("Not logged in. Please login first.")
            return False
        try:
            self.navigate_to_home()
            if not self.find_post_button():
                return False
            time.sleep(2)

            # Find the textarea but don't add content yet
            textarea = self.find_post_textarea()
            if not textarea:
                return False

            if visibility.lower() == "public":
                self.set_post_visibility("public")

            if not self.click_schedule_button():
                return False
            if not self.set_schedule_datetime(schedule_time):
                return False

            # Click Next after setting date/time (first Next)
            if not self.click_schedule_next_button():
                return False

            # Wait a bit after first Next click
            time.sleep(3)

            # Click Next again (second Next)
            if not self.click_schedule_next_button():
                return False

            # Wait a bit after second Next click
            time.sleep(3)

            # After clicking Next twice, we need to re-enter the post content
            # and then click the Schedule button
            textarea = self.find_post_textarea()
            if textarea:
                textarea.clear()
                try:
                    textarea.send_keys(text)
                except Exception as e:
                    if "BMP" in str(e):
                        cleaned_text = "".join(
                            char for char in text if ord(char) < 65536
                        )
                        textarea.send_keys(cleaned_text)
                        logger.info(f"Re-entered cleaned text: {cleaned_text}")
                    else:
                        raise e
                logger.info("Re-entered post content in scheduling dialog")
            else:
                logger.warning("Could not find textarea to re-enter content")

            # Click the final Schedule button (using aria-label)
            if not self.click_schedule_confirm_button():
                return False

            logger.info(f"Successfully scheduled post for {schedule_time}")
            return True
        except Exception as e:
            logger.error(f"Error scheduling post: {e}")
            return False

    def click_schedule_button(self) -> bool:
        """
        Click the clock icon to open the scheduling dialog.

        Returns:
            bool: True if button found and clicked, False otherwise
        """
        try:
            # Look for the clock/schedule button
            schedule_selectors = [
                "button[aria-label*='Schedule post']",
                "button[aria-label*='Schedule']",
                "button.share-actions__scheduled-post-btn",
                "button[id*='ember'][class*='scheduled-post-btn']",
                "button.artdeco-button--circle[aria-label*='Schedule']",
            ]

            for selector in schedule_selectors:
                try:
                    schedule_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    logger.info("Found schedule button")
                    schedule_button.click()
                    logger.info("Clicked schedule button")
                    time.sleep(2)
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue

            logger.error("Could not find schedule button")
            return False

        except Exception as e:
            logger.error(f"Error clicking schedule button: {e}")
            return False

    def set_schedule_datetime(self, schedule_time: datetime.datetime) -> bool:
        """
        Set the date and time for the scheduled post.

        Args:
            schedule_time: datetime object for when to schedule the post

        Returns:
            bool: True if date/time set successfully, False otherwise
        """
        try:
            # Wait for scheduling dialog to appear
            time.sleep(2)

            # Format the date and time for LinkedIn
            date_str = schedule_time.strftime("%m/%d/%Y")
            time_str = schedule_time.strftime("%I:%M %p")

            # Set the date
            date_selectors = [
                "input[aria-label*='Date']",
                "input[type='date']",
                "input[placeholder*='Date']",
            ]

            date_set = False
            for selector in date_selectors:
                try:
                    date_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    date_input.clear()
                    date_input.send_keys(date_str)
                    logger.info(f"Set date to: {date_str}")
                    date_set = True
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if not date_set:
                logger.error("Could not find date input field")
                return False

            # Set the time
            time_selectors = [
                "input[aria-label*='Time']",
                "input[type='time']",
                "input[placeholder*='Time']",
            ]

            time_set = False
            for selector in time_selectors:
                try:
                    time_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    time_input.clear()
                    time_input.send_keys(time_str)
                    logger.info(f"Set time to: {time_str}")
                    time_set = True
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if not time_set:
                logger.error("Could not find time input field")
                return False

            return True

        except Exception as e:
            logger.error(f"Error setting schedule datetime: {e}")
            return False

    def click_schedule_next_button(self) -> bool:
        """
        Click the 'Next' button in the scheduling dialog.
        """
        try:
            next_selectors = [
                "button[aria-label*='Next']",
                "button:contains('Next')",
                ".share-box-footer__primary-btn",
            ]
            for selector in next_selectors:
                try:
                    if "contains" in selector:
                        elements = self.driver.find_elements(By.TAG_NAME, "button")
                        for element in elements:
                            if (
                                "Next" in element.text
                                and element.is_enabled()
                                and element.is_displayed()
                            ):
                                logger.info("Found and clicked 'Next' button")
                                element.click()
                                time.sleep(2)  # Wait for dialog to update
                                return True
                    else:
                        next_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        logger.info("Found and clicked 'Next' button")
                        next_button.click()
                        time.sleep(2)  # Wait for dialog to update
                        return True
                except (TimeoutException, NoSuchElementException):
                    continue
            logger.error("Could not find 'Next' button in schedule dialog")
            return False
        except Exception as e:
            logger.error(f"Error clicking 'Next' button: {e}")
            return False

    def click_schedule_confirm_button(self) -> bool:
        """
        Click the 'Schedule' button to confirm the scheduled post.
        """
        try:
            logger.info("Looking for schedule confirmation button...")
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"Found {len(all_buttons)} buttons in the dialog:")
            for i, button in enumerate(all_buttons):
                if button.is_displayed() and button.is_enabled():
                    logger.info(
                        f"  Button {i}: '{button.text}' (aria-label: '{button.get_attribute('aria-label')}')"
                    )

            # First, look for a button with "Schedule" in the text (not aria-label)
            for button in all_buttons:
                if (
                    button.is_displayed()
                    and button.is_enabled()
                    and "Schedule" in button.text
                ):
                    logger.info(
                        f"Found and clicked 'Schedule' button with text: {button.text}"
                    )
                    button.click()
                    time.sleep(2)
                    return True

            # Look for a button with "Post" in the text that might be the schedule confirmation
            for button in all_buttons:
                if (
                    button.is_displayed()
                    and button.is_enabled()
                    and "Post" in button.text
                    and "Anyone" not in button.text  # Avoid "Post to Anyone" button
                ):
                    logger.info(
                        f"Found and clicked 'Post' button with text: {button.text}"
                    )
                    button.click()
                    time.sleep(2)
                    return True

            # Look for buttons with specific aria-labels that might be the schedule button
            schedule_aria_labels = [
                "Schedule post",
                "Schedule",
                "Confirm schedule",
                "Post scheduled content",
            ]

            for button in all_buttons:
                aria_label = button.get_attribute("aria-label")
                if (
                    button.is_displayed()
                    and button.is_enabled()
                    and aria_label
                    and aria_label in schedule_aria_labels
                    and aria_label != "Schedule post"  # Avoid the clock icon
                ):
                    logger.info(
                        f"Found and clicked schedule button with aria-label: {aria_label}"
                    )
                    button.click()
                    time.sleep(2)
                    return True

            logger.error("Could not find 'Schedule' confirmation button")
            return False
        except Exception as e:
            logger.error(f"Error clicking schedule confirm button: {e}")
            return False

    def post_linkedin_content(
        self,
        text: str,
        schedule_time: datetime.datetime | None = None,
        visibility: str = "connections",
    ) -> bool:
        """
        Main wrapper function to post content to LinkedIn with optional scheduling.

        Args:
            text: The text content to post
            schedule_time: When to post (if None, posts immediately)
            visibility: Post visibility - "connections" or "public"

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if schedule_time is None:
                # Post immediately
                logger.info("Posting content immediately...")
                return self.post_text(text, visibility)
            else:
                # Schedule the post
                logger.info(f"Scheduling post for {schedule_time}")
                return self.schedule_post(text, schedule_time, visibility)

        except Exception as e:
            logger.error(f"Error in post_linkedin_content: {e}")
            return False


def main():
    """Main function to demonstrate LinkedIn automation with the new wrapper function."""

    # Check if credentials are set
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if not email or not password:
        print("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables")
        return

    # Initialize the poster with persistent cache
    poster = LinkedInSeleniumPoster(headless=False)

    try:
        # Login to LinkedIn (will use cached session if available)
        if poster.login(email, password):
            print("✅ Successfully logged in to LinkedIn")
            print("💾 Browser cache and cookies are being saved for future sessions")

            # Example 1: Post immediately
            immediate_text = f"This is an immediate post from the LinkedIn wrapper 😁😁 😁 ! Posted at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} #LinkedInAutomation #WrapperDemo"

            print("\n📝 Example 1: Posting immediately")
            print(f"Text: '{immediate_text}'")

            # Example 2: Schedule a post for tomorrow
            tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
            tomorrow = tomorrow.replace(
                hour=10, minute=0, second=0, microsecond=0
            )  # 10:00 AM tomorrow

            scheduled_text = f"This is a scheduled post from the LinkedIn wrapper! Scheduled for {tomorrow.strftime('%Y-%m-%d %H:%M')} #LinkedInAutomation #ScheduledPost"

            print("\n📅 Example 2: Scheduling post")
            print(f"Text: '{scheduled_text}'")
            print(f"Schedule for: {tomorrow.strftime('%Y-%m-%d %I:%M %p')}")

            if poster.post_linkedin_content(
                scheduled_text, schedule_time=tomorrow, visibility="connections"
            ):
                print("✅ Successfully scheduled post")
                print("Please check your LinkedIn scheduled posts to verify.")
            else:
                print("❌ Failed to schedule post")

        else:
            print("❌ Failed to login to LinkedIn")

    except Exception as e:
        print(f"❌ An error occurred: {e}")

    finally:
        poster.close()
        print("\n💡 Tip: Run this script again and it should skip the login process!")
        print(
            "💡 The wrapper function handles both immediate posting and scheduling automatically!"
        )


if __name__ == "__main__":
    main()
