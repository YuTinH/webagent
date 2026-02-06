from playwright.sync_api import sync_playwright
import time
import re

class BrowserEnv:
    def __init__(self, headless=True):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            base_url="http://localhost:8014"
        )
        self.page = self.context.new_page()

    def reset(self, start_url):
        try:
            self.page.goto(start_url)
            self.page.wait_for_load_state('networkidle', timeout=5000)
        except: 
            pass # Ignore timeout on initial load
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
                if (node.className) attrs.push('.' + node.className.split(' ').join('.'));
                if (node.getAttribute('type')) attrs.push('type="' + node.getAttribute('type') + '"');
                if (node.getAttribute('placeholder')) attrs.push('placeholder="' + node.getAttribute('placeholder') + '"');
                if (node.getAttribute('role')) attrs.push('role="' + node.getAttribute('role') + '"');
                
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
        try:
            content = self.page.evaluate(script)
            # Cleanup excessive whitespace
            content = re.sub(r'\s+', ' ', content).strip()
            # Truncate if too long (simple protection)
            if len(content) > 10000: content = content[:10000] + "...(truncated)"
            
            url = self.page.url
            return f"URL: {url}\nCONTENT:\n{content}"
        except Exception as e:
            return f"Error getting observation: {e}"

    def step(self, action_cmd):
        """
        Executes a string command from LLM.
        Formats: CLICK(sel), TYPE(sel, text), SELECT(sel, val), GOTO(url), DONE()
        """
        print(f"🤖 Executing: {action_cmd}")
        
        try:
            if action_cmd.startswith("CLICK"):
                match = re.match(r"CLICK\((.*?)\)", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    self.page.click(sel, timeout=5000)
                    return True, "Clicked"
            
            elif action_cmd.startswith("TYPE"):
                match = re.match(r"TYPE\((.*?),\s*(.*)\)", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    text = match.group(2).strip().strip('"').strip("'")
                    self.page.fill(sel, text, timeout=5000)
                    return True, "Typed"
            
            elif action_cmd.startswith("SELECT"):
                match = re.match(r"SELECT\((.*?),\s*(.*)\)", action_cmd)
                if match:
                    sel = match.group(1).strip().strip('"').strip("'")
                    val = match.group(2).strip().strip('"').strip("'")
                    self.page.select_option(sel, val, timeout=5000)
                    return True, "Selected"
            
            elif action_cmd.startswith("GOTO"):
                match = re.match(r"GOTO\((.*?)\)", action_cmd)
                if match:
                    url = match.group(1).strip().strip('"').strip("'")
                    
                    # Robustly handle LLM hallucinated domains like http://bank.local
                    if "localhost:8014" not in url:
                        # Strip existing scheme if any
                        url = re.sub(r'^https?://', '', url)
                        # Ensure path starts with /
                        if not url.startswith('/'): url = '/' + url
                        # Prepend our server root
                        url = "http://localhost:8014" + url
                        
                    self.page.goto(url)
                    return True, "Navigated"
            
            elif action_cmd.startswith("DONE"):
                return False, "Done" # Stop loop
            
            self.page.wait_for_load_state('networkidle', timeout=2000)
            
        except Exception as e:
            print(f"❌ Execution Error: {e}")
            return True, f"Error: {e}" # Continue loop but report error
            
        return True, "Unknown Command"

    def close(self):
        self.browser.close()
        self.playwright.stop()
