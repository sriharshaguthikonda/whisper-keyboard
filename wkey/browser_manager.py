import os
import time
import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    SessionNotCreatedException,
)
import pickle
import json


class BrowserManager:
    def __init__(
        self, webdriver_path, user_data_dir=None, profile_dir=None, headless=False
    ):
        self.webdriver_path = webdriver_path
        self.user_data_dir = user_data_dir
        self.profile_dir = profile_dir
        self.headless = headless
        self.driver = None
        self.session_file = "browser_session.pkl"
        self.max_retries = 3
        self.retry_delay = 2
        self.setup_logging()

    def setup_logging(self):
        self.logger = logging.getLogger("BrowserManager")
        self.logger.setLevel(logging.INFO)

    def create_options(self) -> Options:
        """Create browser options with custom settings"""
        options = Options()
        if self.user_data_dir:
            options.add_argument(f"user-data-dir={self.user_data_dir}")
        if self.profile_dir:
            options.add_argument(f"profile-directory={self.profile_dir}")
        options.add_argument("--remote-allow-origins=*")
        if self.headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
        return options

    def save_session(self):
        """Save the current session information"""
        if self.driver:
            session_data = {
                "session_id": self.driver.session_id,
                "executor_url": self.driver.command_executor._url,
            }
            with open(self.session_file, "wb") as f:
                pickle.dump(session_data, f)

    def load_session(self) -> bool:
        """Load a saved session if available"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, "rb") as f:
                    session_data = pickle.load(f)
                    return session_data
        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")
        return None

    def start_driver(self) -> None:
        """Initialize or recover the WebDriver"""
        session_data = self.load_session()

        if session_data:
            try:
                self.driver = self.recover_session(session_data)
                if self.check_driver_health():
                    self.logger.info("Successfully recovered session")
                    return
            except Exception as e:
                self.logger.warning(f"Failed to recover session: {e}")

        # Start new session if recovery failed
        self.create_new_session()

    def recover_session(self, session_data):
        """Attempt to recover an existing session"""
        driver = webdriver.Remote(command_executor=session_data["executor_url"])
        driver.session_id = session_data["session_id"]
        return driver

    def create_new_session(self):
        """Create a fresh browser session"""
        options = self.create_options()
        service = Service(self.webdriver_path)

        for attempt in range(self.max_retries):
            try:
                self.driver = webdriver.Edge(service=service, options=options)
                self.save_session()
                self.logger.info("New session created successfully")
                return
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        raise WebDriverException("Failed to create new session after multiple attempts")

    def check_driver_health(self) -> bool:
        """Verify if the current driver session is healthy"""
        try:
            self.driver.current_url
            return True
        except:
            return False

    def safe_execute(self, action_func, *args, **kwargs):
        """Execute browser actions with automatic recovery"""
        for attempt in range(self.max_retries):
            try:
                if not self.check_driver_health():
                    self.restart_driver()
                return action_func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Action failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    self.restart_driver()
                    time.sleep(self.retry_delay)
        raise WebDriverException("Action failed after multiple attempts")

    def restart_driver(self):
        """Restart the browser completely"""
        self.quit()
        self.start_driver()

    def quit(self):
        """Clean up browser resources"""
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass
        finally:
            self.driver = None

    def find_element_safely(self, by, value, timeout=10):
        """Find element with wait and retry logic"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.error(f"Element not found: {by}={value}")
            raise

    # Spotify-specific methods
    def play_song(self):
        """Play current track with error handling"""

        def _play():
            play_button = self.find_element_safely(
                By.XPATH, "//button[@aria-label='Play']"
            )
            play_button.click()
            self.change_device()

        return self.safe_execute(_play)

    def pause_song(self):
        """Pause current track with error handling"""

        def _pause():
            pause_button = self.find_element_safely(
                By.XPATH, "//button[@aria-label='Pause']"
            )
            pause_button.click()

        return self.safe_execute(_pause)

    def next_track(self):
        """Skip to next track with error handling"""

        def _next():
            next_button = self.find_element_safely(
                By.XPATH, "//button[@aria-label='Next']"
            )
            next_button.click()

        return self.safe_execute(_next)

    def previous_track(self):
        """Go to previous track with error handling"""

        def _previous():
            prev_button = self.find_element_safely(
                By.XPATH, "//button[@aria-label='Previous']"
            )
            prev_button.click()

        return self.safe_execute(_previous)

    def change_device(self):
        """Change playback device with error handling"""

        def _change_device():
            devices_button = self.find_element_safely(
                By.XPATH, "//button[@aria-label='Connect to a device']"
            )
            devices_button.click()
            time.sleep(2)

            device_picker = self.find_element_safely(
                By.XPATH, '//*[@id="device-picker"]'
            )
            device_picker.click()
            time.sleep(2)

            browser_option = self.find_element_safely(
                By.XPATH, '//*[text()="This web browser"]'
            )
            browser_option.click()

        return self.safe_execute(_change_device)
