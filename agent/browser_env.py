from playwright.sync_api import sync_playwright
import time
import re
import threading
import os
import json
import tempfile
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from runtime_paths import server_base_url


_PLAYWRIGHT_LAUNCH_LOCK = threading.Lock()


def _should_log_actions() -> bool:
    return os.environ.get("WEBAGENT_SUPPRESS_ACTION_LOGS", "").strip().lower() not in {"1", "true", "yes", "on"}


def _normalize_option_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _normalize_dom_id(value):
    return re.sub(r"[-_]+", "", str(value or "").strip().lower())


def _normalize_toggle_value(value):
    raw = _normalize_option_text(value)
    if raw in {"1", "true", "yes", "on", "check", "checked", "select", "selected", "enable", "enabled"}:
        return True
    if raw in {"0", "false", "no", "off", "uncheck", "unchecked", "deselect", "disable", "disabled"}:
        return False
    return None


def _simple_id_selector_variants(selector):
    match = re.fullmatch(r"#([A-Za-z0-9_-]+)", str(selector or "").strip())
    if not match:
        return [selector]
    token = match.group(1)
    sep_positions = [idx for idx, ch in enumerate(token) if ch in {"-", "_"}]
    if not sep_positions:
        return [selector]
    variants = []
    seen = set()
    total = 1 << len(sep_positions)
    for mask in range(total):
        chars = list(token)
        for bit_index, pos in enumerate(sep_positions):
            chars[pos] = "_" if ((mask >> bit_index) & 1) else "-"
        candidate = "#" + "".join(chars)
        if candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)
    if selector in seen:
        variants.remove(selector)
        variants.insert(0, selector)
    return variants


def _leading_id_selector(selector):
    match = re.match(r"^(#([A-Za-z0-9_-]+))(?:\s+.+)?$", str(selector or "").strip())
    if not match:
        return None
    return match.group(1)


def _normalize_datetime_local_value(value):
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", raw):
        return raw.replace(" ", "T")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}", raw):
        return raw[:-3] + ":" + raw[-2:]
    return raw


def _normalize_selector_syntax(selector):
    raw = re.sub(r"\s+", " ", str(selector or "").strip())
    if not raw:
        return raw
    raw = re.sub(
        r":contains\(\s*([\"'])(.*?)\1\s*\)",
        lambda m: f":has-text({m.group(1)}{m.group(2)}{m.group(1)})",
        raw,
    )
    raw = re.sub(
        r"\[onclick\s*=\s*([\"'])([A-Za-z_][A-Za-z0-9_$.]*)\1\s*\]",
        lambda m: f"[onclick*={m.group(1)}{m.group(2)}{m.group(1)}]",
        raw,
    )
    return raw


def _selector_fallback_variants(selector):
    raw = _normalize_selector_syntax(selector)
    if not raw:
        return []

    variants = []
    seen = set()

    def _add(candidate):
        value = str(candidate or "").strip()
        if value and value not in seen:
            seen.add(value)
            variants.append(value)

    _add(raw)

    onclick_match = re.search(
        r"\[onclick\*?=\s*([\"'])([A-Za-z_][A-Za-z0-9_$.]*)\1\s*\]",
        raw,
    )
    if onclick_match:
        fn_name = onclick_match.group(2)
        _add(f'[onclick*="{fn_name}"]')
        _add(f'button[onclick*="{fn_name}"]')
        _add(f'a[onclick*="{fn_name}"]')

    return variants


def _bounded_edit_distance(a, b, max_distance=2):
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        row_min = curr[0]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            ))
            row_min = min(row_min, curr[-1])
        if row_min > max_distance:
            return max_distance + 1
        prev = curr
    return prev[-1]

class BrowserEnv:
    def __init__(self, headless=True, base_url=None, task_id=None, binding_task_id=None, allowed_domains=None, task_inputs=None):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.task_id = str(task_id or "").strip()
        self.binding_task_id = str(binding_task_id or task_id or "").strip()
        self.task_inputs = dict(task_inputs or {})
        self.base_url = (base_url or server_base_url()).rstrip("/")
        self.allowed_domains = []
        for domain in allowed_domains or []:
            normalized = str(domain or "").strip().lower()
            if normalized and normalized not in self.allowed_domains:
                self.allowed_domains.append(normalized)
        try:
            # Playwright sync startup races when multiple browser processes are
            # spawned concurrently in the same worker process. Serialize launch.
            with _PLAYWRIGHT_LAUNCH_LOCK:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(headless=headless, timeout=60000)
                self.context = self.browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    base_url=self.base_url
                )
                init_chunks = []
                if self.task_id:
                    init_chunks.append(
                        f"window.__WEBAGENT_TASK_ID__ = {json.dumps(self.task_id)};"
                    )
                if self.binding_task_id:
                    init_chunks.append(
                        f"window.__WEBAGENT_BINDING_TASK_ID__ = {json.dumps(self.binding_task_id)};"
                    )
                if self.task_inputs:
                    init_chunks.append(
                        f"window.__WEBAGENT_TASK_INPUTS__ = {json.dumps(self.task_inputs)};"
                    )
                if init_chunks:
                    self.context.add_init_script(script="".join(init_chunks))
                self.page = self.context.new_page()
        except Exception:
            self.close()
            raise

    def _resolve_upload_filepath(self, raw_path):
        candidate = str(raw_path or "").strip()
        if not candidate:
            raise ValueError("empty_upload_path")

        if os.path.exists(candidate):
            return candidate

        basename = os.path.basename(candidate)
        if not basename:
            raise ValueError(f"invalid_upload_path:{candidate}")

        stub_dir = Path(tempfile.gettempdir()) / "webagent_upload_stubs"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub_path = stub_dir / basename
        if not stub_path.exists():
            stub_path.write_bytes(b"webagent-upload-stub\n")
        return str(stub_path)

    def _resolve_locator(self, selector, timeout=10000):
        selector = _normalize_selector_syntax(selector)
        last_error = None
        for selector_variant in _selector_fallback_variants(selector):
            for candidate in _simple_id_selector_variants(selector_variant):
                target = self.page.locator(candidate)
                try:
                    target.wait_for(state="attached", timeout=timeout)
                    return candidate, target
                except Exception as exc:
                    last_error = exc
        leading_id = _leading_id_selector(selector)
        if leading_id and leading_id != str(selector or "").strip():
            for candidate in _simple_id_selector_variants(leading_id):
                target = self.page.locator(candidate)
                try:
                    target.wait_for(state="attached", timeout=timeout)
                    return candidate, target
                except Exception as exc:
                    last_error = exc
        match = re.fullmatch(r"#([A-Za-z0-9_-]+)", str(selector or "").strip())
        if match:
            wanted = match.group(1).lower()
            wanted_norm = _normalize_dom_id(wanted)
            try:
                dom_ids = self.page.evaluate(
                    "() => Array.from(document.querySelectorAll('[id]')).map(el => String(el.id || ''))"
                )
            except Exception:
                dom_ids = []
            best_id = None
            best_distance = 3
            containment_id = None
            containment_delta = None
            for dom_id in dom_ids:
                candidate = str(dom_id or "").strip()
                if not candidate:
                    continue
                candidate_norm = _normalize_dom_id(candidate)
                if wanted_norm and candidate_norm and (
                    candidate_norm.endswith(wanted_norm) or wanted_norm.endswith(candidate_norm)
                ):
                    delta = abs(len(candidate_norm) - len(wanted_norm))
                    if containment_delta is None or delta < containment_delta:
                        containment_id = candidate
                        containment_delta = delta
                distance = _bounded_edit_distance(wanted, candidate.lower(), max_distance=2)
                if distance < best_distance:
                    best_distance = distance
                    best_id = candidate
            if containment_id:
                target = self.page.locator(f"#{containment_id}")
                target.wait_for(state="attached", timeout=timeout)
                return f"#{containment_id}", target
            if best_id and best_distance <= 2:
                target = self.page.locator(f"#{best_id}")
                target.wait_for(state="attached", timeout=timeout)
                return f"#{best_id}", target
        raise last_error

    def _retarget_health_records_click(self, selector, target):
        try:
            current_url = str(self.page.url or "").lower()
        except Exception:
            current_url = ""
        if "/health.local/records.html" not in current_url:
            return None

        normalized_selector = _normalize_selector_syntax(selector)
        lowered_selector = normalized_selector.lower()
        if (
            "#records-list" not in lowered_selector
            and "prescription -" not in lowered_selector
            and "refills-" not in lowered_selector
        ):
            return None

        try:
            info = target.evaluate(
                """el => {
                    const card = el.closest('.record-card');
                    const button = card ? card.querySelector('button[data-rx-id], button.btn.pri') : null;
                    return {
                        tag: (el.tagName || '').toLowerCase(),
                        role: String(el.getAttribute('role') || '').toLowerCase(),
                        hasOnclick: !!el.getAttribute('onclick'),
                        rxId: String(el.getAttribute('data-rx-id') || '').trim(),
                        buttonRxId: button ? String(button.getAttribute('data-rx-id') || '').trim() : '',
                    };
                }"""
            )
        except Exception:
            return None

        tag = str(info.get("tag") or "").lower()
        role = str(info.get("role") or "").lower()
        is_interactive = (
            tag in {"button", "a", "input", "select", "textarea", "summary"}
            or role in {"button", "link", "tab", "checkbox", "radio", "switch"}
            or bool(info.get("hasOnclick"))
        )
        if is_interactive:
            return None

        rx_id = str(info.get("rxId") or info.get("buttonRxId") or "").strip()
        if not rx_id:
            return None

        button_selector = f"button[data-rx-id='{rx_id}']"
        button_target = self.page.locator(button_selector)
        button_target.wait_for(state="attached", timeout=1000)
        return button_selector, button_target

    def _wait_until_stable(self):
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=10000)
        except Exception:
            pass
        try:
            self.page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(250)

    def _resolve_navigation_url(self, raw_url):
        url = (raw_url or "").strip()
        if not url:
            return self.base_url

        if url.startswith(self.base_url):
            return url

        local_host_match = re.match(
            r"^(?:https?://)?(?:localhost|127\.0\.0\.1):\d+(?P<path>/.*)$",
            url,
            flags=re.IGNORECASE,
        )
        if local_host_match:
            return self.base_url + local_host_match.group("path")

        if url.startswith(("http://", "https://")):
            parts = urlsplit(url)
            if parts.hostname in {"localhost", "127.0.0.1"}:
                base_parts = urlsplit(self.base_url)
                return urlunsplit(
                    (
                        base_parts.scheme,
                        base_parts.netloc,
                        parts.path or "/",
                        parts.query,
                        parts.fragment,
                    )
                )
            return url

        if not url.startswith("/"):
            url = "/" + url
        return self.base_url + url

    def _effective_domain(self, raw_url):
        parts = urlsplit(str(raw_url or "").strip())
        host = (parts.hostname or "").strip().lower()
        if host in {"localhost", "127.0.0.1"}:
            path = (parts.path or "").lstrip("/")
            if "/" in path:
                return path.split("/", 1)[0].lower()
            return ""
        return host

    def _navigation_allowed(self, raw_url):
        if not self.allowed_domains:
            return True, self._effective_domain(raw_url)
        effective_domain = self._effective_domain(raw_url)
        if not effective_domain:
            return True, effective_domain
        return effective_domain in self.allowed_domains, effective_domain

    def reset(self, start_url):
        try:
            self.page.goto(self._resolve_navigation_url(start_url), wait_until='domcontentloaded', timeout=15000)
        except Exception:
            pass
        self._wait_until_stable()
        return self.get_observation()

    def get_observation(self):
        """
        Returns a simplified text representation of the current page.
        Ideally, this would be an Accessibility Tree, but a simplified HTML dump 
        is easier to implement robustly without accessibility API flakiness.
        """
        # Inject script to get simplified DOM
        # We identify interactable elements and give them IDs/hints
        
        script = r"""
        (() => {
            function getSimplifiedDOM(node) {
                if (node.nodeType === Node.TEXT_NODE) {
                    var text = node.textContent.trim();
                    return text ? text : null;
                }
                
                if (node.nodeType !== Node.ELEMENT_NODE) return null;
                
                var tag = node.tagName.toLowerCase();
                if (['script', 'style', 'noscript', 'meta', 'link', 'svg', 'path'].indexOf(tag) !== -1) return null;
                
                var style = window.getComputedStyle(node);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return null;

                var attrs = [];
                if (node.id) attrs.push('#' + node.id);
                if (node.getAttribute('data-original-id')) attrs.push('data-original-id="' + node.getAttribute('data-original-id') + '"');
                if (node.className) attrs.push('.' + node.className.split(' ').join('.'));
                if (node.getAttribute('name')) attrs.push('name="' + node.getAttribute('name') + '"');
                if (node.getAttribute('type')) attrs.push('type="' + node.getAttribute('type') + '"');
                if (node.getAttribute('placeholder')) attrs.push('placeholder="' + node.getAttribute('placeholder') + '"');
                if (node.getAttribute('role')) attrs.push('role="' + node.getAttribute('role') + '"');
                if (node.getAttribute('title')) attrs.push('title="' + node.getAttribute('title') + '"');
                if (node.getAttribute('aria-label')) attrs.push('aria-label="' + node.getAttribute('aria-label') + '"');
                if (node.getAttribute('onclick')) {
                    var onclick = node.getAttribute('onclick') || '';
                    var fnMatch = onclick.match(/^\s*([A-Za-z0-9_$.]+)/);
                    var onclickHint = fnMatch ? fnMatch[1] : onclick.slice(0, 64);
                    if (onclickHint) attrs.push('onclick="' + onclickHint + '"');
                }
                if (tag === 'a' && node.getAttribute('href')) attrs.push('href="' + node.getAttribute('href') + '"');
                if ((tag === 'input' || tag === 'textarea') && node.value) attrs.push('value="' + node.value + '"');
                if (tag === 'input' && (node.type === 'checkbox' || node.type === 'radio')) attrs.push(node.checked ? 'checked' : 'unchecked');
                if (tag === 'select') {
                    var options = Array.from(node.options || []).map(function(opt) {
                        var label = (opt.textContent || '').trim();
                        var value = (opt.value || '').trim();
                        return value === label || !label ? value : (value + ':' + label);
                    }).filter(Boolean);
                    if (options.length) attrs.push('options="' + options.join(' | ') + '"');
                }
                
                var childrenStr = '';
                node.childNodes.forEach(function(child) {
                    var res = getSimplifiedDOM(child);
                    if (res) childrenStr += (res + ' ');
                });
                
                var isInteractive = ['a', 'button', 'input', 'select', 'textarea'].indexOf(tag) !== -1 || node.getAttribute('role') === 'button';
                var hasContent = childrenStr.trim().length > 0;
                
                if (isInteractive || hasContent) {
                    var attrStr = attrs.length > 0 ? ' ' + attrs.join(' ') : '';
                    return '<' + tag + attrStr + '>' + childrenStr.trim() + '</' + tag + '>';
                }
                
                return childrenStr.trim();
            }
            
            return getSimplifiedDOM(document.body);
        })()
        """
        last_error = None
        for _ in range(3):
            try:
                self._wait_until_stable()
                content = self.page.evaluate(script)
                content = re.sub(r'\s+', ' ', content).strip()
                if len(content) > 10000:
                    content = content[:10000] + "...(truncated)"
                url = self.page.url
                return f"URL: {url}\nCONTENT:\n{content}"
            except Exception as e:
                last_error = e
                self.page.wait_for_timeout(300)
        return f"Error getting observation: {last_error}"

    def _select_with_fallback(self, selector, raw_value):
        sel = selector.strip().strip('"').strip("'")
        raw = raw_value.strip().strip('"').strip("'")
        target = self.page.locator(sel)
        target.wait_for(state="attached", timeout=10000)

        options = target.locator("option")
        option_count = 0
        for _ in range(12):
            try:
                option_count = options.count()
            except Exception:
                option_count = 0
            if option_count > 0:
                break
            self.page.wait_for_timeout(250)

        attempts = []
        if raw.startswith("label:"):
            label = raw[len("label:"):].strip()
            if label:
                attempts.append(("label", label))
        else:
            if raw:
                attempts.append(("value", raw))
                attempts.append(("label", raw))

        seen = set()
        for mode, candidate in attempts:
            key = (mode, candidate)
            if key in seen or not candidate:
                continue
            seen.add(key)
            try:
                if mode == "label":
                    target.select_option(label=candidate, timeout=10000)
                else:
                    target.select_option(value=candidate, timeout=10000)
                return
            except Exception:
                pass

        option_count = options.count()
        desired = _normalize_option_text(raw.replace("label:", "", 1))
        fallback_value = None
        partial_value = None
        for idx in range(option_count):
            opt = options.nth(idx)
            option_value = (opt.get_attribute("value") or "").strip()
            option_label = (opt.text_content() or "").strip()
            normalized_value = _normalize_option_text(option_value)
            normalized_label = _normalize_option_text(option_label)
            normalized_pair = _normalize_option_text(f"{option_value}:{option_label}")
            if desired in {normalized_value, normalized_label, normalized_pair}:
                fallback_value = option_value or option_label
                break
            if desired and (
                desired in normalized_value
                or desired in normalized_label
                or normalized_value in desired
                or normalized_label in desired
            ):
                partial_value = partial_value or option_value or option_label
        if not fallback_value and partial_value:
            fallback_value = partial_value
        if fallback_value:
            if any(ch in fallback_value for ch in (" ", "/", "(", ")")):
                try:
                    target.select_option(label=fallback_value, timeout=10000)
                    return
                except Exception:
                    pass
            target.select_option(value=fallback_value, timeout=10000)
            return

        if option_count:
            available = []
            for idx in range(option_count):
                opt = options.nth(idx)
                option_value = (opt.get_attribute("value") or "").strip()
                option_label = (opt.text_content() or "").strip()
                if option_value and option_label and option_value != option_label:
                    available.append(f"{option_value}:{option_label}")
                elif option_value:
                    available.append(option_value)
                elif option_label:
                    available.append(option_label)
            raise RuntimeError(
                "did not find some options: requested={!r} available={}".format(raw, available[:12])
            )

        # Some pages expose radio-card or div-based choices and agents still
        # express them as SELECT(...). Fall back to clicking the best text/value
        # match instead of treating this as an unsupported action type.
        desired = _normalize_option_text(raw.replace("label:", "", 1))
        candidate_nodes = target.locator("*")
        try:
            node_count = candidate_nodes.count()
        except Exception:
            node_count = 0
        best_index = None
        partial_index = None
        for idx in range(node_count):
            node = candidate_nodes.nth(idx)
            try:
                text_value = (node.text_content() or "").strip()
                data_reason = (node.get_attribute("data-reason") or "").strip()
                data_value = (node.get_attribute("value") or "").strip()
                aria_label = (node.get_attribute("aria-label") or "").strip()
            except Exception:
                continue
            candidates = [
                _normalize_option_text(text_value),
                _normalize_option_text(data_reason),
                _normalize_option_text(data_value),
                _normalize_option_text(aria_label),
            ]
            if desired and desired in candidates:
                best_index = idx
                break
            if desired and any(
                desired in candidate or candidate in desired
                for candidate in candidates
                if candidate
            ):
                partial_index = partial_index if partial_index is not None else idx
        chosen_index = best_index if best_index is not None else partial_index
        if chosen_index is not None:
            candidate_nodes.nth(chosen_index).click(timeout=10000, force=True)
            return

        raise RuntimeError(f"did not find some options: requested={raw!r} available=[]")

    def _locator_tag_info(self, selector):
        sel = selector.strip().strip('"').strip("'")
        sel, target = self._resolve_locator(sel, timeout=10000)
        try:
            info = target.evaluate(
                """el => ({
                    tag: (el.tagName || '').toLowerCase(),
                    type: ((el.getAttribute('type') || el.type || '') + '').toLowerCase(),
                    role: ((el.getAttribute('role') || '') + '').toLowerCase()
                })"""
            )
        except Exception:
            info = {}
        return target, str(info.get("tag") or "").lower(), str(info.get("type") or "").lower(), str(info.get("role") or "").lower()

    def _set_checkable_state(self, target, input_type, raw_value):
        desired = _normalize_toggle_value(raw_value)
        if input_type == "radio":
            try:
                already_checked = bool(target.evaluate("el => !!el.checked"))
            except Exception:
                already_checked = False
            if already_checked:
                target.click(timeout=10000)
                return "Checked"
            target.check(timeout=10000)
            return "Checked"
        if desired is False:
            target.uncheck(timeout=10000)
            return "Unchecked"
        target.check(timeout=10000)
        return "Checked"

    def step(self, action_cmd):
        """
        Executes a string command from LLM.
        Formats: CLICK(sel), TYPE(sel, text), SELECT(sel, val), CHECK(sel), UNCHECK(sel), UPLOAD(sel, filepath), GOTO(url), WAIT(), DONE()
        """
        display_action = action_cmd if len(action_cmd) <= 240 else action_cmd[:240] + "...(truncated)"
        if _should_log_actions():
            print(f"🤖 Executing: {display_action}")
        
        try:
            if action_cmd.startswith("CLICK"):
                match = re.match(r"^CLICK\((.*)\)$", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    if "," in sel:
                        sel = sel.split(",", 1)[0].strip().strip('"').strip("'")
                    resolved_sel, target = self._resolve_locator(sel, timeout=10000)
                    retargeted = self._retarget_health_records_click(resolved_sel, target)
                    if retargeted is not None:
                        resolved_sel, target = retargeted
                    try:
                        target.click(timeout=10000)
                    except Exception as click_err:
                        if "intercepts pointer events" not in str(click_err).lower():
                            raise
                        self.page.wait_for_timeout(300)
                        self.page.locator(resolved_sel).click(timeout=3000, force=True)
                    self._wait_until_stable()
                    return True, "Clicked"
            
            elif action_cmd.startswith("TYPE"):
                match = re.match(r"^TYPE\((.*?),\s*(.*)\)$", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    text = match.group(2).strip().strip('"').strip("'")
                    target, tag, input_type, role = self._locator_tag_info(sel)
                    if tag == "select":
                        self._select_with_fallback(sel, text)
                        self._wait_until_stable()
                        return True, "Selected"
                    if tag == "input" and input_type in {"checkbox", "radio"}:
                        status = self._set_checkable_state(target, input_type, text)
                        self._wait_until_stable()
                        return True, status
                    button_like = (
                        tag in {"button", "a", "summary"}
                        or input_type in {"button", "submit", "checkbox", "radio"}
                        or role in {"button", "checkbox", "radio", "switch", "tab"}
                    )
                    if button_like:
                        visible_text = (target.text_content() or "").strip().lower()
                        value_attr = (target.get_attribute("value") or "").strip().lower()
                        desired = str(text or "").strip().lower()
                        if (
                            not desired
                            or desired == visible_text
                            or desired == value_attr
                            or desired in visible_text
                            or desired in value_attr
                        ):
                            target.click(force=True, timeout=10000)
                            self._wait_until_stable()
                            return True, "Clicked"
                    if tag == "input" and input_type == "datetime-local":
                        text = _normalize_datetime_local_value(text)
                    self.page.fill(sel, text, timeout=10000)
                    self._wait_until_stable()
                    return True, "Typed"
            
            elif action_cmd.startswith("SELECT"):
                match = re.match(r"^SELECT\((.*?),\s*(.*)\)$", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    val = match.group(2).strip().strip('"').strip("'")
                    target, tag, input_type, role = self._locator_tag_info(sel)
                    if tag == "input" and input_type in {"checkbox", "radio"}:
                        status = self._set_checkable_state(target, input_type, val)
                        self._wait_until_stable()
                        return True, status
                    if tag in {"input", "textarea"}:
                        if tag == "input" and input_type == "datetime-local":
                            val = _normalize_datetime_local_value(val)
                        self.page.fill(sel, val, timeout=10000)
                        self._wait_until_stable()
                        return True, "Typed"
                    button_like = (
                        tag in {"button", "a", "summary"}
                        or input_type in {"button", "submit", "checkbox", "radio"}
                        or role in {"button", "checkbox", "radio", "switch", "tab"}
                    )
                    if button_like:
                        target.click(force=True, timeout=10000)
                        self._wait_until_stable()
                        return True, "Clicked"
                    self._select_with_fallback(sel, val)
                    self._wait_until_stable()
                    return True, "Selected"

            elif action_cmd.startswith("CHECK"):
                match = re.match(r"^CHECK\((.*?)(?:,\s*(.*))?\)$", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    raw_val = match.group(2).strip().strip('"').strip("'") if match.group(2) else "checked"
                    target, _, input_type, _ = self._locator_tag_info(sel)
                    status = self._set_checkable_state(target, input_type, raw_val or "checked")
                    self._wait_until_stable()
                    return True, status

            elif action_cmd.startswith("UNCHECK"):
                match = re.match(r"^UNCHECK\((.*?)(?:,\s*(.*))?\)$", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    raw_val = match.group(2).strip().strip('"').strip("'") if match.group(2) else "unchecked"
                    target, _, input_type, _ = self._locator_tag_info(sel)
                    status = self._set_checkable_state(target, input_type, raw_val or "unchecked")
                    self._wait_until_stable()
                    return True, status

            elif action_cmd.startswith("UPLOAD"):
                match = re.match(r"^UPLOAD\((.*?),\s*(.*)\)$", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    filepath = match.group(2).strip().strip('"').strip("'")
                    target, tag, input_type, _ = self._locator_tag_info(sel)
                    if tag in {"input", "textarea"} and input_type != "file":
                        # Several synthetic tasks model uploads as filename text
                        # fields. Treat UPLOAD on those controls as entering the
                        # filename rather than calling set_input_files on a text box.
                        target.fill(os.path.basename(filepath) or filepath, timeout=10000)
                        self._wait_until_stable()
                        return True, "Typed"
                    resolved_path = self._resolve_upload_filepath(filepath)
                    self.page.set_input_files(sel, resolved_path, timeout=10000)
                    self._wait_until_stable()
                    return True, "Uploaded"
            
            elif action_cmd.startswith("GOTO"):
                match = re.match(r"^GOTO\((.*)\)$", action_cmd)
                if match:
                    url = match.group(1).strip().strip('"').strip("'")
                    if not re.match(r"^https?://", url, re.IGNORECASE):
                        return True, "Error: goto_requires_url"

                    url = self._resolve_navigation_url(url)
                    allowed, effective_domain = self._navigation_allowed(url)
                    if not allowed:
                        return True, f"Error: goto_domain_blocked:{effective_domain or 'unknown'}"

                    self.page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    self._wait_until_stable()
                    return True, "Navigated"

            elif action_cmd.startswith("WAIT"):
                self.page.wait_for_timeout(1000)
                self._wait_until_stable()
                return True, "Waited"
            
            elif action_cmd.startswith("DONE"):
                return False, "Done" # Stop loop
            
            # Global Wait for network to settle
            self.page.wait_for_load_state('networkidle', timeout=10000)
            time.sleep(0.5)
            
        except Exception as e:
            if _should_log_actions():
                print(f"❌ Execution Error: {e}")
            return True, f"Error: {e}" # Continue loop but report error
            
        return True, "Error: Unknown Command"

    def close(self):
        with _PLAYWRIGHT_LAUNCH_LOCK:
            try:
                if self.page is not None:
                    self.page.close()
            except Exception:
                pass
            try:
                if self.context is not None:
                    self.context.close()
            except Exception:
                pass
            try:
                if self.browser is not None:
                    self.browser.close()
            except Exception:
                pass
            try:
                if self.playwright is not None:
                    self.playwright.stop()
            except Exception:
                pass
