"""Playwright browser controller.

Runs the Playwright sync API inside a QThread so it never blocks the
PySide6 event loop.  All communication back to the UI happens through
Qt signals.

Architecture
------------
BrowserController (QThread)
  ├── launched with a session's EventRecorder and ScreenshotService
  ├── opens a Chromium browser via playwright.sync_api
  ├── listens to context.on("page") to detect every new tab/popup
  ├── attaches JS listeners to EVERY page (tab) via _attach_page_listeners()
  ├── tracks self._active_page — the most recently navigated/opened tab
  └── emits Qt signals that the MainWindow connects to for UI updates

Multi-tab support
-----------------
When the agent opens a link in a new tab (Ctrl+click, right-click → new tab,
window.open(), etc.) Playwright fires context.on("page", new_page).
_on_new_page() immediately attaches all listeners to that page so every tab
is fully recorded.  self._active_page always points to the tab that last
received a navigation event, which is used for screenshots and status display.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from PySide6.QtCore import QThread, Signal

from app.config import BROWSER_CHANNEL, BROWSER_HEADLESS, SCREENSHOT_ON_CLICK, SCREENSHOT_ON_NAVIGATION
from app.recorder.event_recorder import EventRecorder
from app.recorder.screenshot_service import ScreenshotService

logger = logging.getLogger(__name__)

# JavaScript injected into every page to report clicks and input changes
# back to Python via page.expose_function.
_JS_INJECT = """
(function() {
    if (window.__t502_injected) return;
    window.__t502_injected = true;

    document.addEventListener('click', function(e) {
        var el = e.target;
        var info = {
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            text: (el.innerText || el.textContent || '').trim().substring(0, 200),
            id: el.id || '',
            name: el.name || el.getAttribute('name') || '',
            url: window.location.href || '',
            title: document.title || '',
            x: e.clientX,
            y: e.clientY
        };
        // Try to build a simple selector
        if (el.id) info.selector = '#' + el.id;
        else if (el.name) info.selector = el.tagName.toLowerCase() + '[name="' + el.name + '"]';
        else info.selector = el.tagName ? el.tagName.toLowerCase() : '';
        window.__t502_on_click(info);
    }, true);

    document.addEventListener('change', function(e) {
        var el = e.target;
        var info = {
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            type: el.type || 'text',
            name: el.name || el.getAttribute('name') || '',
            id: el.id || '',
            placeholder: el.placeholder || '',
            url: window.location.href || '',
            title: document.title || '',
            value: el.value || ''
        };
        if (el.id) info.selector = '#' + el.id;
        else if (el.name) info.selector = el.tagName.toLowerCase() + '[name="' + el.name + '"]';
        else info.selector = el.tagName ? el.tagName.toLowerCase() : '';
        window.__t502_on_input(info);
    }, true);

    // Detect search form submissions (Enter key in search inputs)
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter') return;
        var el = e.target;
        var role = el.getAttribute('role') || '';
        var type = (el.type || '').toLowerCase();
        var isSearch = (type === 'search' || role === 'combobox' ||
                        (el.name || '').toLowerCase().indexOf('q') === 0 ||
                        (el.name || '').toLowerCase().indexOf('search') >= 0);
        if (isSearch) {
            var info = {
                tag: el.tagName ? el.tagName.toLowerCase() : '',
                type: type,
                name: el.name || '',
                id: el.id || '',
                url: window.location.href || '',
                title: document.title || '',
                value: el.value || ''
            };
            window.__t502_on_search(info);
        }
    }, true);
})();
"""


class BrowserController(QThread):
    """QThread that owns the Playwright browser lifecycle."""

    # Signals emitted from the worker thread — connect to UI slots
    page_navigated = Signal(str, str)        # url, title
    click_recorded = Signal(str, str, dict)  # url, title, click_info dict
    input_recorded = Signal(str, str, dict)  # url, title, input_info dict
    search_recorded = Signal(str, str, dict) # url, title, search_info dict
    browser_closed = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        event_recorder: EventRecorder,
        screenshot_service: ScreenshotService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._event_recorder = event_recorder
        self._screenshot_service = screenshot_service
        self._active_page = None   # the most recently navigated tab
        self._browser = None
        self._playwright = None
        self._running = False
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Launch the browser. Runs in the worker thread."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                self._playwright = pw
                browser = pw.chromium.launch(
                    headless=BROWSER_HEADLESS,
                    channel=BROWSER_CHANNEL if BROWSER_CHANNEL != "chromium" else None,
                )
                self._browser = browser
                self._running = True

                # Set stop_event when the browser process disconnects
                browser.on("disconnected", lambda: self._stop_event.set())

                context = browser.new_context()

                # Listen for every new tab/popup opened in this context
                context.on("page", self._on_new_page)

                # Inject JS into every page/navigation (all tabs) automatically
                context.add_init_script(_JS_INJECT)

                # Open the initial tab
                first_page = context.new_page()
                self._active_page = first_page
                self._attach_page_listeners(first_page)
                first_page.goto("about:blank")

                # Block until the browser is closed (any tab or the window X button)
                self._stop_event.wait()

        except Exception as exc:
            logger.exception("Browser error")
            self.error_occurred.emit(str(exc))
        finally:
            self._running = False
            self._stop_event.set()  # ensure stop() doesn't hang
            self.browser_closed.emit()

    # ------------------------------------------------------------------
    # New-tab handler
    # ------------------------------------------------------------------

    def _on_new_page(self, page) -> None:
        """Called by Playwright when any new tab or popup is opened."""
        logger.debug("New tab opened: %s", page.url)
        self._active_page = page
        self._attach_page_listeners(page)

    def _attach_page_listeners(self, page) -> None:
        """Attach all recording listeners to a Playwright page object.

        Uses default-argument capture (p=page) so each closure holds a
        reference to its own page, not a shared variable.
        """
        page.on(
            "framenavigated",
            lambda frame, p=page: self._on_navigation(frame, p),
        )
        page.on(
            "close",
            lambda p=page: self._on_page_closed(p),
        )
        try:
            page.expose_function(
                "__t502_on_click",
                lambda info, p=page: self._on_click_js(info, p),
            )
            page.expose_function(
                "__t502_on_input",
                lambda info, p=page: self._on_input_js(info, p),
            )
            page.expose_function(
                "__t502_on_search",
                lambda info, p=page: self._on_search_js(info, p),
            )
        except Exception:
            # expose_function can fail if the page is already closed/navigated
            logger.debug("Could not expose functions on page %s", page.url, exc_info=True)

    # ------------------------------------------------------------------
    # Browser event handlers (called from Playwright's internal thread)
    # ------------------------------------------------------------------

    def _on_navigation(self, frame, page) -> None:
        if not self._running:
            return
        if frame != page.main_frame:
            return
        if self._event_recorder.is_paused:
            return
        if page.is_closed():
            return

        # Make this the active page so screenshots and status use it
        self._active_page = page
        url = frame.url

        try:
            title = page.title()
        except Exception:
            title = ""

        screenshot_path = None
        if SCREENSHOT_ON_NAVIGATION:
            screenshot_path = self._screenshot_service.take_screenshot(
                page, f"navigation_{self._sanitize_label(url)}"
            )

        self._event_recorder.record_navigation(url, title, screenshot_path)
        self.page_navigated.emit(url, title)

    def _on_page_closed(self, page) -> None:
        """When a tab is closed, fall back to another open page if possible."""
        if self._active_page is page:
            self._active_page = None
        logger.debug("Tab closed: %s", page.url)

    def _on_click_js(self, info: dict, page) -> None:
        if self._event_recorder.is_paused:
            return
        # IMPORTANT: avoid sync Playwright calls here (page.url/page.title/screenshot)
        # because this callback runs in Playwright's binding event loop.
        url = info.get("url", "")
        title = info.get("title", "")

        screenshot_path = None
        if SCREENSHOT_ON_CLICK:
            logger.debug("Skipping click screenshot in JS binding callback to avoid event-loop blocking")

        self._event_recorder.record_click(
            url=url,
            title=title,
            selector=info.get("selector"),
            element_text=info.get("text"),
            element_tag=info.get("tag"),
            coordinates={"x": info.get("x"), "y": info.get("y")},
            screenshot_path=screenshot_path,
        )
        self.click_recorded.emit(url, title, info)

    def _on_input_js(self, info: dict, page) -> None:
        if self._event_recorder.is_paused:
            return
        url = info.get("url", "")
        title = info.get("title", "")

        self._event_recorder.record_input(
            url=url,
            title=title,
            value=info.get("value", ""),
            input_type=info.get("type", "text"),
            input_name=info.get("name", ""),
            field_id=info.get("id", ""),
            field_placeholder=info.get("placeholder", ""),
            selector=info.get("selector"),
        )
        self.input_recorded.emit(url, title, info)

    def _on_search_js(self, info: dict, page) -> None:
        if self._event_recorder.is_paused:
            return
        url = info.get("url", "")
        title = info.get("title", "")

        self._event_recorder.record_search(
            url=url,
            title=title,
            query=info.get("value", ""),
            form_selector=info.get("selector"),
        )
        self.search_recorded.emit(url, title, info)

    # ------------------------------------------------------------------
    # Public control methods (called from main thread)
    # ------------------------------------------------------------------

    def get_current_url(self) -> str:
        try:
            return self._active_page.url if self._active_page else ""
        except Exception:
            return ""

    def get_current_title(self) -> str:
        try:
            return self._active_page.title() if self._active_page else ""
        except Exception:
            return ""

    def get_page(self):
        """Return the active Playwright page (for screenshot/snapshot calls)."""
        return self._active_page

    def stop(self) -> None:
        """Gracefully close the browser from any thread."""
        self._running = False
        self._stop_event.set()
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            logger.debug("Error closing browser during stop()", exc_info=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_label(url: str) -> str:
        from urllib.parse import urlparse
        from app.utils.paths import safe_filename
        try:
            parsed = urlparse(url)
            label = parsed.netloc + parsed.path
        except Exception:
            label = url
        return safe_filename(label, max_len=30)
