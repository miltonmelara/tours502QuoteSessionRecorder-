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
  ├── tracks ALL open pages in self._all_pages
  └── polls every 500 ms (in the Playwright sync thread) for URL changes
      so navigation is captured regardless of browser event threading

Navigation strategy
-------------------
Playwright fires page events (framenavigated, etc.) from its internal
asyncio loop — a different thread from the QThread that owns the sync API.
Calling any sync Playwright method (page.title, page.url, etc.) OR emitting
Qt signals from that asyncio context causes greenlet/thread errors.

Solution: the main loop polls active_page.url every 500 ms from WITHIN the
Playwright sync thread (run()), where all sync API calls are safe and Qt
signals can be emitted without crossing event-loop boundaries.

JS callbacks (click, input, search) are called from the asyncio context too,
so they ONLY write to a thread-safe queue — no sync Playwright calls, no Qt
signals, no exceptions.
"""

from __future__ import annotations

import logging
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal

from app.config import (
    BROWSER_CHANNEL,
    BROWSER_EXECUTABLE_CANDIDATES,
    BROWSER_EXECUTABLE_PATH,
    BROWSER_FALLBACK_CHANNELS,
    BROWSER_HEADLESS,
    BROWSER_PASSIVE_DOMAINS,
    BROWSER_PROFILE_DIR,
    BROWSER_USE_PERSISTENT_PROFILE,
    SCREENSHOT_ON_NAVIGATION,
)
from app.recorder.event_recorder import EventRecorder
from app.recorder.screenshot_service import ScreenshotService

logger = logging.getLogger(__name__)
_PASSIVE_DOMAINS_JS = json.dumps([domain.lower() for domain in BROWSER_PASSIVE_DOMAINS])

# ---------------------------------------------------------------------------
# JavaScript injected into every page load.
# Wraps every window.__t502_* call in try/catch so a missing binding never
# breaks the page or silences subsequent events.
# ---------------------------------------------------------------------------
_JS_INJECT = """
(function() {
    var host = (window.location.hostname || '').toLowerCase();
    var passiveDomains = __PASSIVE_DOMAINS__;
    for (var i = 0; i < passiveDomains.length; i++) {
        var domain = passiveDomains[i];
        if (host === domain || host.endsWith('.' + domain)) return true;
    }

    if (window.__t502_injected) return true;
    window.__t502_injected = true;

    function nowPayload(type, payload) {
        payload = payload || {};
        payload.event_type = type;
        payload.url = window.location.href || payload.url || '';
        payload.title = document.title || payload.title || '';
        payload.browser_ts = new Date().toISOString();
        return payload;
    }

    function safeCall(payload) {
        try {
            if (typeof window.__t502_record_event === 'function') {
                window.__t502_record_event(payload);
            }
        } catch (e) {
            /* Never let recorder instrumentation break the website. */
        }
    }

    function textOf(el) {
        return ((el && (el.innerText || el.textContent)) || '').trim().replace(/\\s+/g, ' ').substring(0, 200);
    }

    function selectorOf(el) {
        if (!el) return '';
        var tag = (el.tagName || 'el').toLowerCase();
        if (el.id) return '#' + el.id;
        var name = el.name || (el.getAttribute ? el.getAttribute('name') : '');
        if (name) return tag + '[name="' + name + '"]';
        var cls = (el.className && typeof el.className === 'string') ? el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '';
        return cls ? tag + '.' + cls : tag;
    }

    function elementPayload(el) {
        el = el || document.body;
        return {
            tag: (el.tagName || '').toLowerCase(),
            text: textOf(el),
            id: el.id || '',
            name: el.name || (el.getAttribute ? el.getAttribute('name') : '') || '',
            href: el.href || (el.closest ? ((el.closest('a') || {}).href || '') : ''),
            selector: selectorOf(el)
        };
    }

    document.addEventListener('pointerdown', function(e) {
        var payload = elementPayload(e.target || e.srcElement || document.body);
        payload.x = e.clientX;
        payload.y = e.clientY;
        payload.button = e.button;
        payload.pointer_type = e.pointerType || 'mouse';
        payload.alt_key = !!e.altKey;
        payload.ctrl_key = !!e.ctrlKey;
        payload.meta_key = !!e.metaKey;
        payload.shift_key = !!e.shiftKey;
        safeCall(nowPayload('click', payload));
    }, true);

    function inputPayload(e) {
        var el = e.target || document.body;
        var payload = elementPayload(el);
        payload.type = el.type || 'text';
        payload.placeholder = el.placeholder || '';
        payload.value = el.value || '';
        payload.input_event = e.type;
        safeCall(nowPayload('input', payload));
    }

    document.addEventListener('change', inputPayload, true);
    document.addEventListener('input', function(e) {
        var tag = ((e.target || {}).tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') inputPayload(e);
    }, true);

    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter') return;
        var el = e.target || document.body;
        var role = (el.getAttribute ? el.getAttribute('role') : '') || '';
        var type = (el.type || '').toLowerCase();
        var name = (el.name || '').toLowerCase();
        var isSearch = type === 'search' || role === 'combobox' ||
                       role === 'searchbox' ||
                       name.indexOf('q') === 0 ||
                       name.indexOf('search') >= 0 ||
                       name.indexOf('query') >= 0;
        if (!isSearch) return;
        var payload = elementPayload(el);
        payload.type = type;
        payload.value = el.value || '';
        safeCall(nowPayload('search_submitted', payload));
    }, true);

    function emitVNav(reason, extra) {
        safeCall(nowPayload('page_navigated', {
            navigation_kind: 'virtual',
            reason: reason,
            detail: extra || null
        }));
    }

    var _push = history.pushState;
    history.pushState = function() {
        var r = _push.apply(this, arguments);
        emitVNav('history.pushState');
        return r;
    };
    var _replace = history.replaceState;
    history.replaceState = function() {
        var r = _replace.apply(this, arguments);
        emitVNav('history.replaceState');
        return r;
    };
    window.addEventListener('popstate', function() { emitVNav('popstate'); }, true);
    window.addEventListener('hashchange', function() { emitVNav('hashchange'); }, true);

    var lastScrollAt = 0;
    window.addEventListener('scroll', function() {
        var now = Date.now();
        if (now - lastScrollAt < 700) return;
        lastScrollAt = now;
        var doc = document.documentElement || document.body;
        safeCall(nowPayload('scroll', {
            x: window.scrollX || 0,
            y: window.scrollY || 0,
            viewport_width: window.innerWidth || 0,
            viewport_height: window.innerHeight || 0,
            document_width: Math.max(doc.scrollWidth || 0, document.body ? document.body.scrollWidth || 0 : 0),
            document_height: Math.max(doc.scrollHeight || 0, document.body ? document.body.scrollHeight || 0 : 0)
        }));
    }, true);

    var mutScore = 0, mutTimer = null, lastMutEmit = 0, lastMutTarget = null;
    function flushMutation() {
        var now = Date.now();
        var score = mutScore;
        var target = lastMutTarget;
        mutScore = 0;
        lastMutTarget = null;
        if (score < 8) return;
        if ((now - lastMutEmit) < 1200) return;
        lastMutEmit = now;
        safeCall(nowPayload('ui_changed', {
            selector: selectorOf(target),
            tag: target && target.tagName ? target.tagName.toLowerCase() : '',
            text: textOf(target),
            mutation_score: score
        }));
    }

    new MutationObserver(function(muts) {
        for (var i = 0; i < muts.length; i++) {
            var m = muts[i];
            if (m.target && (m.target.tagName || '').toLowerCase() === 'script') continue;
            mutScore += (m.addedNodes || []).length;
            mutScore += (m.removedNodes || []).length;
            if (m.type === 'attributes') mutScore += 1;
            lastMutTarget = m.target || lastMutTarget;
        }
        if (mutTimer) clearTimeout(mutTimer);
        mutTimer = setTimeout(flushMutation, 350);
    }).observe(document.documentElement || document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style', 'aria-expanded', 'aria-hidden', 'hidden']
    });

    safeCall(nowPayload('ui_changed', {
        selector: 'document',
        tag: 'document',
        text: 'recorder instrumentation attached',
        mutation_score: 0,
        recorder_event: 'instrumentation_attached'
    }));
    return true;
})();
""".replace("__PASSIVE_DOMAINS__", _PASSIVE_DOMAINS_JS)


class BrowserController(QThread):
    """QThread that owns the Playwright browser lifecycle."""

    # Signals — emitted from the Playwright QThread (safe)
    page_navigated = Signal(str, str)   # url, title
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

        # All open pages — written from asyncio callbacks, read from poll loop.
        # CPython GIL makes simple list.append / list copy safe here.
        self._all_pages: List = []
        self._active_page = None

        # Cached URL/title — updated in poll loop (sync thread)
        self._active_url = ""
        self._active_title = ""

        # Per-page last-recorded URL for deduplication
        self._page_last_url: Dict[int, str] = {}
        self._page_last_frame_url: Dict[int, str] = {}
        self._page_handlers_attached: set[int] = set()
        self._passive_page_ids: set[int] = set()

        self._browser = None
        self._context = None
        self._playwright = None
        self._running = False
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # QThread entry point — everything here runs in the Playwright thread
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Launch browser and run the poll loop. Runs in the QThread."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                self._playwright = pw
                context, browser = self._launch_browser_context(pw)
                self._context = context
                self._browser = browser
                self._running = True

                if browser is not None:
                    browser.on("disconnected", lambda: self._stop_event.set())

                # Expose one generic event bridge at context level. This keeps
                # recorder-side event handling extensible and avoids silent
                # misses when we add a new browser event type.
                context.expose_function("__t502_record_event", self._on_browser_event_js)

                # Register new-tab/popup detector BEFORE creating any page.
                context.on("page", self._on_new_page)

                # Inject JS into every page load automatically.
                context.add_init_script(_JS_INJECT)

                # Open the first tab.
                first_page = context.pages[0] if context.pages else context.new_page()
                self._all_pages.append(first_page)
                self._active_page = first_page
                self._attach_minimal_page_handlers(first_page)
                if not first_page.url or first_page.url == "about:blank":
                    first_page.goto("about:blank")

                # ── POLL LOOP ────────────────────────────────────────────
                # Runs entirely in this QThread — safe to call sync Playwright
                # API and emit Qt signals.
                while not self._stop_event.wait(timeout=0.5):
                    self._poll_all_pages()

                try:
                    context.close()
                except Exception:
                    logger.debug("Browser context close failed in Playwright thread", exc_info=True)

        except Exception as exc:
            logger.exception("Browser error")
            self.error_occurred.emit(str(exc))
        finally:
            self._running = False
            self._stop_event.set()
            self.browser_closed.emit()

    def _launch_browser_context(self, pw):
        """Launch the preferred installed browser and return (context, browser)."""
        if BROWSER_USE_PERSISTENT_PROFILE:
            return self._launch_persistent_browser_context(pw)

        browser = self._launch_ephemeral_browser(pw)
        return browser.new_context(), browser

    def _launch_persistent_browser_context(self, pw):
        """Launch Chrome with a dedicated persistent user data directory."""
        user_data_dir = str(BROWSER_PROFILE_DIR)
        BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        for executable_path in self._browser_executable_paths():
            try:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=BROWSER_HEADLESS,
                    executable_path=executable_path,
                )
                logger.info(
                    "Browser launched with persistent profile %s and executable path: %s",
                    user_data_dir,
                    executable_path,
                )
                return context, context.browser
            except Exception as exc:
                logger.warning(
                    "Could not launch persistent browser executable %r; trying next fallback. Error: %s",
                    executable_path,
                    exc,
                )

        attempted: list[str] = []
        channels = [BROWSER_CHANNEL, *BROWSER_FALLBACK_CHANNELS]
        for channel in channels:
            if not channel or channel in attempted:
                continue
            attempted.append(channel)
            try:
                launch_kwargs = {"headless": BROWSER_HEADLESS}
                if channel != "chromium":
                    launch_kwargs["channel"] = channel
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    **launch_kwargs,
                )
                logger.info(
                    "Browser launched with persistent profile %s and Playwright channel: %s",
                    user_data_dir,
                    channel,
                )
                return context, context.browser
            except Exception as exc:
                logger.warning(
                    "Could not launch persistent browser channel %r; trying next fallback. Error: %s",
                    channel,
                    exc,
                )
        raise RuntimeError(
            "Could not launch any configured persistent browser channel: "
            + ", ".join(attempted)
        )

    def _launch_ephemeral_browser(self, pw):
        """Launch the preferred installed browser, falling back if unavailable."""
        for executable_path in self._browser_executable_paths():
            try:
                browser = pw.chromium.launch(
                    headless=BROWSER_HEADLESS,
                    executable_path=executable_path,
                )
                logger.info("Browser launched with executable path: %s", executable_path)
                return browser
            except Exception as exc:
                logger.warning(
                    "Could not launch browser executable %r; trying next fallback. Error: %s",
                    executable_path,
                    exc,
                )

        attempted: list[str] = []
        channels = [BROWSER_CHANNEL, *BROWSER_FALLBACK_CHANNELS]
        for channel in channels:
            if not channel or channel in attempted:
                continue
            attempted.append(channel)
            try:
                launch_kwargs = {"headless": BROWSER_HEADLESS}
                if channel != "chromium":
                    launch_kwargs["channel"] = channel
                browser = pw.chromium.launch(**launch_kwargs)
                logger.info("Browser launched with Playwright channel: %s", channel)
                return browser
            except Exception as exc:
                logger.warning(
                    "Could not launch browser channel %r; trying next fallback. Error: %s",
                    channel,
                    exc,
                )
        raise RuntimeError(
            "Could not launch any configured browser channel: "
            + ", ".join(attempted)
        )

    @staticmethod
    def _browser_executable_paths() -> list[str]:
        configured = [BROWSER_EXECUTABLE_PATH] if BROWSER_EXECUTABLE_PATH else []
        paths: list[str] = []
        for raw_path in [*configured, *BROWSER_EXECUTABLE_CANDIDATES]:
            if not raw_path or raw_path in paths:
                continue
            if Path(raw_path).exists():
                paths.append(raw_path)
        return paths

    def _poll_all_pages(self) -> None:
        """Check every open page for URL changes. Called from the sync thread."""
        self._refresh_pages_from_context()
        pages_snapshot = list(self._all_pages)  # safe copy under GIL
        for page in pages_snapshot:
            try:
                if page.is_closed():
                    continue
            except Exception:
                continue

            live_location = self._read_live_location(page)
            if live_location is None:
                continue

            url = live_location.get("url", "")
            title = live_location.get("title", "")

            if not url or url in ("about:blank", ""):
                continue
            if self._event_recorder.is_paused:
                continue

            page_id = id(page)
            if url == self._page_last_url.get(page_id):
                continue  # URL unchanged since last poll

            self._page_last_url[page_id] = url
            self._active_page = page
            self._active_url = url
            passive_mode = self._is_passive_url(url)
            if passive_mode:
                self._passive_page_ids.add(page_id)

            # Record and notify immediately. Title/screenshot calls can lag on
            # busy sites; the URL visit itself should never wait on them.
            self._event_recorder.record_navigation(
                url,
                title,
                metadata={"navigation_kind": "url_seen"},
            )
            self.page_navigated.emit(url, title)

            # Update active-page tracking
            self._active_title = title
            if not passive_mode:
                self._ensure_page_instrumented(page)

            logger.debug("Poll: navigation detected %s", url)
            screenshot_path = None
            if SCREENSHOT_ON_NAVIGATION and not passive_mode:
                screenshot_path = self._screenshot_service.take_screenshot(
                    page,
                    f"navigation_{self._sanitize_label(url)}",
                )
            self._event_recorder.record_navigation(
                url,
                title,
                screenshot_path=screenshot_path,
                metadata={"navigation_kind": "page_load"},
            )
            self.page_navigated.emit(url, title)

    def _read_live_location(self, page) -> Optional[dict]:
        """Ask the actual page for its current URL/title.

        ``page.url`` can lag behind when the sync dispatcher has not processed
        pending browser events yet. Evaluating in the page forces a live round
        trip to the tab the user is actually looking at.
        """
        try:
            page_id = id(page)
            raw_url = page.url or ""
            if page_id in self._passive_page_ids or self._is_passive_url(raw_url):
                return {"url": raw_url, "title": ""}
        except Exception:
            pass

        try:
            result = page.evaluate(
                "() => ({ url: window.location.href || '', title: document.title || '' })"
            )
            if isinstance(result, dict):
                return {
                    "url": str(result.get("url") or ""),
                    "title": str(result.get("title") or ""),
                }
        except Exception:
            logger.debug("Live page location read failed", exc_info=True)

        try:
            return {"url": page.url or "", "title": ""}
        except Exception:
            return None

    def _refresh_pages_from_context(self) -> None:
        """Keep page tracking aligned with Playwright's live context pages."""
        if self._context is None:
            return
        try:
            context_pages = list(self._context.pages)
        except Exception:
            return
        known = {id(page) for page in self._all_pages}
        for page in context_pages:
            if id(page) not in known:
                self._all_pages.append(page)
                self._attach_minimal_page_handlers(page)

    # ------------------------------------------------------------------
    # New-tab / page-close handlers  (called from asyncio — keep minimal)
    # ------------------------------------------------------------------

    def _on_new_page(self, page) -> None:
        """Called when any new tab or popup opens — asyncio context."""
        logger.debug("New tab opened")
        self._all_pages.append(page)
        self._active_page = page
        self._attach_minimal_page_handlers(page)

    def _on_page_closed(self, page) -> None:
        """Called when a tab closes — asyncio context."""
        try:
            self._all_pages.remove(page)
        except ValueError:
            pass
        self._page_last_url.pop(id(page), None)
        self._page_last_frame_url.pop(id(page), None)
        self._page_handlers_attached.discard(id(page))
        self._passive_page_ids.discard(id(page))
        if self._active_page is page:
            self._active_page = self._all_pages[-1] if self._all_pages else None
        logger.debug("Tab closed")

    def _attach_minimal_page_handlers(self, page) -> None:
        page_id = id(page)
        if page_id in self._page_handlers_attached:
            return
        self._page_handlers_attached.add(page_id)
        page.on("close", lambda p=page: self._on_page_closed(p))
        page.on("framenavigated", lambda frame, p=page: self._on_frame_navigated(frame, p))

    def _on_frame_navigated(self, frame, page) -> None:
        """Record main-frame navigations immediately, including fast redirects."""
        try:
            if self._event_recorder.is_paused:
                return
            if frame != page.main_frame:
                return
            url = frame.url
        except Exception:
            return

        if not url or url in ("about:blank", ""):
            return

        page_id = id(page)
        if url == self._page_last_frame_url.get(page_id):
            return
        self._page_last_frame_url[page_id] = url
        self._active_page = page
        self._active_url = url
        if self._is_passive_url(url):
            self._passive_page_ids.add(page_id)

        self._event_recorder.record_navigation(
            url,
            "",
            metadata={"navigation_kind": "frame_navigated"},
        )

    # ------------------------------------------------------------------
    # JS → Python callbacks  (called from Playwright's asyncio thread)
    # Rules: NO sync Playwright API calls, NO Qt signal emissions,
    #        only thread-safe queue operations.
    # ------------------------------------------------------------------

    def _on_browser_event_js(self, info: dict) -> None:
        event_type = info.get("event_type", "")
        if event_type == "click":
            self._on_click_js(info)
        elif event_type == "input":
            self._on_input_js(info)
        elif event_type == "search_submitted":
            self._on_search_js(info)
        elif event_type == "page_navigated":
            self._on_virtual_nav_js(info)
        elif event_type == "scroll":
            self._on_scroll_js(info)
        elif event_type == "ui_changed":
            self._on_ui_changed_js(info)

    def _cache_browser_location(self, info: dict) -> None:
        url = info.get("url") or ""
        title = info.get("title") or ""
        if url:
            self._active_url = url
        if title:
            self._active_title = title

    def _on_click_js(self, info: dict) -> None:
        try:
            if self._event_recorder.is_paused:
                return
            self._cache_browser_location(info)
            self._event_recorder.record_click(
                url=info.get("url", ""),
                title=info.get("title", ""),
                selector=info.get("selector"),
                element_text=info.get("text"),
                element_tag=info.get("tag"),
                coordinates={"x": info.get("x"), "y": info.get("y")},
                screenshot_path=None,
                metadata={
                    "href": info.get("href"),
                    "button": info.get("button"),
                    "pointer_type": info.get("pointer_type"),
                    "alt_key": info.get("alt_key"),
                    "ctrl_key": info.get("ctrl_key"),
                    "meta_key": info.get("meta_key"),
                    "shift_key": info.get("shift_key"),
                    "browser_ts": info.get("browser_ts"),
                },
            )
        except Exception:
            logger.debug("_on_click_js error", exc_info=True)

    def _on_input_js(self, info: dict) -> None:
        try:
            if self._event_recorder.is_paused:
                return
            self._cache_browser_location(info)
            self._event_recorder.record_input(
                url=info.get("url", ""),
                title=info.get("title", ""),
                value=info.get("value", ""),
                input_type=info.get("type", "text"),
                input_name=info.get("name", ""),
                field_id=info.get("id", ""),
                field_placeholder=info.get("placeholder", ""),
                selector=info.get("selector"),
            )
        except Exception:
            logger.debug("_on_input_js error", exc_info=True)

    def _on_search_js(self, info: dict) -> None:
        try:
            if self._event_recorder.is_paused:
                return
            self._cache_browser_location(info)
            self._event_recorder.record_search(
                url=info.get("url", ""),
                title=info.get("title", ""),
                query=info.get("value", ""),
                form_selector=info.get("selector"),
            )
        except Exception:
            logger.debug("_on_search_js error", exc_info=True)

    def _on_virtual_nav_js(self, info: dict) -> None:
        try:
            if self._event_recorder.is_paused:
                return
            self._cache_browser_location(info)
            self._event_recorder.record_navigation(
                info.get("url", ""),
                info.get("title", ""),
                metadata={
                    "navigation_kind": "virtual",
                    "reason": info.get("reason", "unknown"),
                    "detail": info.get("detail"),
                },
            )
        except Exception:
            logger.debug("_on_virtual_nav_js error", exc_info=True)

    def _on_scroll_js(self, info: dict) -> None:
        try:
            if self._event_recorder.is_paused:
                return
            self._cache_browser_location(info)
            self._event_recorder.record_scroll(
                url=info.get("url", ""),
                title=info.get("title", ""),
                coordinates={"x": info.get("x"), "y": info.get("y")},
                metadata={
                    "viewport_width": info.get("viewport_width"),
                    "viewport_height": info.get("viewport_height"),
                    "document_width": info.get("document_width"),
                    "document_height": info.get("document_height"),
                    "browser_ts": info.get("browser_ts"),
                },
            )
        except Exception:
            logger.debug("_on_scroll_js error", exc_info=True)

    def _on_ui_changed_js(self, info: dict) -> None:
        try:
            if self._event_recorder.is_paused:
                return
            self._cache_browser_location(info)
            self._event_recorder.record_ui_change(
                url=info.get("url", ""),
                title=info.get("title", ""),
                selector=info.get("selector"),
                element_text=info.get("text"),
                element_tag=info.get("tag"),
                metadata={
                    "mutation_score": info.get("mutation_score"),
                    "recorder_event": info.get("recorder_event"),
                    "browser_ts": info.get("browser_ts"),
                },
            )
        except Exception:
            logger.debug("_on_ui_changed_js error", exc_info=True)

    def _ensure_page_instrumented(self, page) -> None:
        """Re-apply listeners from the sync thread if a page missed add_init_script."""
        try:
            if self._is_passive_url(page.url or ""):
                self._passive_page_ids.add(id(page))
                return
            page.evaluate(_JS_INJECT)
        except Exception:
            logger.debug("Could not ensure page instrumentation", exc_info=True)

    # ------------------------------------------------------------------
    # Public helpers called from the Qt main thread
    # ------------------------------------------------------------------

    def get_current_url(self) -> str:
        return self._active_url

    def get_current_title(self) -> str:
        return self._active_title

    def get_page(self):
        """Return the active Playwright page (for screenshot calls)."""
        return self._active_page

    def stop(self) -> None:
        """Signal the Playwright thread to close the browser from its own thread."""
        self._running = False
        self._stop_event.set()

    @staticmethod
    def _sanitize_label(url: str) -> str:
        from app.utils.paths import safe_filename

        try:
            parsed = urlparse(url)
            label = f"{parsed.netloc}{parsed.path}"
        except Exception:
            label = url
        return safe_filename(label, max_len=30)

    @staticmethod
    def _is_passive_url(url: str) -> bool:
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            host = ""
        host = host.lower()
        for domain in BROWSER_PASSIVE_DOMAINS:
            domain = domain.lower()
            if host == domain or host.endswith(f".{domain}"):
                return True
        return False
