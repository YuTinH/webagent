import os
import json
import requests

class GLMClient:
    def __init__(self, api_key=None, model="glm-4"):
        self.api_key = api_key or os.environ.get("GLM_API_KEY")
        if not self.api_key:
            raise ValueError("GLM_API_KEY not found in environment variables.")
        
        self.model = model
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions" # Standard GLM-4 Endpoint

    def get_action(self, goal, page_content, history):
        """
        Interacts with the GLM API to determine the next action.
        
        Args:
            goal (str): The user's high-level goal.
            page_content (str): Simplified HTML or Accessibility Tree of the current page.
            history (list): List of previous (observation, action) tuples.
            
        Returns:
            str: The action command (e.g., "CLICK(#btn-submit)").
        """
        
        system_prompt = """You are an autonomous web agent. Your goal is to complete tasks on a simulated website.
You will receive the current page's simplified HTML content and the user's goal.
You must output ONLY the next action to perform. Do not provide explanations.

IMPORTANT: 
1. If you see input fields or buttons relevant to your goal, INTERACT with them (TYPE, SELECT, CLICK). 
2. Do NOT use GOTO unless you are on a completely wrong page (e.g. 404 Not Found).
3. The site is hosted on localhost. Do not hallucinate external domains.

Available actions:
- CLICK(selector): Click an element. Selector should be a valid CSS selector (prefer IDs).
- TYPE(selector, text): Type text into an input field.
- SELECT(selector, value): Select an option from a dropdown.
- GOTO(url): Navigate to a URL (only if stuck or starting).
- DONE(): Task is complete.

Format your response exactly as one of the actions above.
Example: TYPE(#search-input, "laptop")
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"GOAL: {goal}"}
        ]

        # Add history
        for obs, act in history:
            messages.append({"role": "user", "content": f"PAGE STATE:\n{obs}"})
            messages.append({"role": "assistant", "content": act})

        # Current observation
        messages.append({"role": "user", "content": f"CURRENT PAGE STATE:\n{page_content}\n\nWhat is your next action?"})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1, # Low temp for deterministic actions
            "max_tokens": 100
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            return content
        except Exception as e:
            print(f"LLM Call Error: {e}")
            return "ERROR()"
