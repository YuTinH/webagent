import json
import os
import random
import time
from pathlib import Path
from typing import Dict, List

import requests


DEFAULT_SYSTEM_PROMPT = """You are an autonomous web agent. Your goal is to complete tasks on a simulated city website.
You must output ONLY ONE action command per turn and no explanation.
Valid commands:
- CLICK(<selector>)
- TYPE(<selector>, <text>)
- SELECT(<selector>, <value_or_label>)
- UPLOAD(<selector>, <filepath>)
- GOTO(<url>)
- WAIT()
- DONE()
If the goal is already satisfied on the current page, output DONE().

AVAILABLE SITES (ONLY USE THESE):
- http://localhost:8014/shop.local/ (Shopping, Repairs, Housekeeping)
- http://localhost:8014/bank.local/ (Accounts, Cards, Autopay, Budget)
- http://localhost:8014/gov.local/ (Address, Permits, Visa)
- http://localhost:8014/work.local/ (Emails, Calendar, Papers)
- http://localhost:8014/mobile.local/ (SMS, Phone Plans)
- http://localhost:8014/health.local/ (Appointments, Insurance)
- http://localhost:8014/housing.local/ (Real Estate, Leases)

IMPORTANT:
1. DO NOT try to use external sites like Google, Gmail, or Airbnb. Everything you need is on the LOCAL sites listed above.
2. If you see an AD, POPUP, or MODAL overlay (like "Limited Offer", "Important Notice", or "Cookies") that blocks your view, you MUST CLICK the close button (often 'x', 'Close', or 'Decline') FIRST.
3. The site uses ID Obfuscation. Look at the button text and context.
4. Prefer selectors already visible in the page state, especially #id, .class, button text, and input placeholders.
5. If a select element shows options="...", use one of those exact values or labels in SELECT(...).
6. Output exactly one command. Never add chain-of-thought or commentary.
"""


WEBRL_SYSTEM_PROMPT = """You are a web interaction policy being evaluated on a persistent multi-site environment.
Return exactly one next action and nothing else.
Allowed actions:
- CLICK(<selector>)
- TYPE(<selector>, <text>)
- SELECT(<selector>, <value_or_label>)
- UPLOAD(<selector>, <filepath>)
- GOTO(<url>)
- WAIT()
- DONE()

Policy rules:
1. Use only selectors or text cues visible in the current page state.
2. If a popup, ad, cookie notice, or modal blocks the page, close it before anything else.
3. If the goal is already satisfied, output DONE().
4. Do not explain your reasoning.
5. If a select element shows options="...", use one of those exact values or labels in SELECT(...).
"""


def _build_system_prompt() -> str:
    prompt_profile = (os.environ.get("AGENT_PROMPT_PROFILE") or "default").strip().lower()
    if prompt_profile in {"webrl", "rl", "webarena_rl"}:
        return WEBRL_SYSTEM_PROMPT
    return DEFAULT_SYSTEM_PROMPT


def _prompt_profile() -> str:
    return (os.environ.get("AGENT_PROMPT_PROFILE") or "default").strip().lower()


def build_messages(goal: str, page_content: str, history: List, system_prompt: str) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for obs, act in history:
        messages.append({"role": "user", "content": f"PAGE STATE:\n{obs}"})
        messages.append({"role": "assistant", "content": act})
    messages.append(
        {
            "role": "user",
            "content": f"GOAL: {goal}\n\nCURRENT PAGE STATE:\n{page_content}\n\nWhat is your next action?",
        }
    )
    return messages


def _render_plain_prompt(messages: List[Dict[str, str]]) -> str:
    chunks = []
    for msg in messages:
        role = msg.get("role", "user").upper()
        content = msg.get("content", "")
        chunks.append(f"{role}:\n{content}")
    chunks.append("ASSISTANT:")
    return "\n\n".join(chunks)


def _strip_thinking_block(text: str) -> str:
    if "</think>" in text:
        return text.split("</think>", 1)[1].strip()
    return text.strip()


class OpenAICompatibleClient:
    backend_name = "openai_compatible"

    def __init__(self):
        self.api_key = (
            os.environ.get("AGENT_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )
        if not self.api_key:
            raise RuntimeError("Set AGENT_API_KEY or ANTHROPIC_AUTH_TOKEN before using the OpenAI-compatible client.")
        self.base_url = (
            os.environ.get("AGENT_BASE_URL")
            or os.environ.get("ANTHROPIC_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.model = (
            os.environ.get("AGENT_MODEL")
            or os.environ.get("ANTHROPIC_MODEL")
            or "nex-agi/deepseek-v3.1-nex-n1"
        )
        raw_max_tokens = os.environ.get("AGENT_MAX_TOKENS") or os.environ.get("ANTHROPIC_MAX_TOKENS")
        if raw_max_tokens is not None:
            try:
                self.max_tokens = max(32, int(raw_max_tokens))
            except Exception:
                self.max_tokens = 200
        else:
            model_l = self.model.lower()
            if any(name in model_l for name in ("glm-4.7", "glm-4.6", "glm-4.5", "glm-5")):
                self.max_tokens = 512
            else:
                self.max_tokens = 80
        self.temperature = float(os.environ.get("AGENT_TEMPERATURE", "0.0"))
        self.min_request_interval_sec = float(os.environ.get("AGENT_MIN_REQUEST_INTERVAL_SEC", "0.0"))
        self._last_request_ts = 0.0
        raw_disable_thinking = os.environ.get("AGENT_DISABLE_THINKING")
        if raw_disable_thinking is None:
            self.disable_thinking = "glm-4.7" in self.model.lower()
        else:
            self.disable_thinking = raw_disable_thinking.strip().lower() == "true"
        self.system_prompt = _build_system_prompt()
        print(
            f"🚀 Client initialized | backend: {self.backend_name} | "
            f"model: {self.model} | max_tokens: {self.max_tokens}"
        )

    def _chat_completions_url(self):
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if "/api/paas/v4" in self.base_url:
            return f"{self.base_url}/chat/completions"
        if self.base_url.endswith("/v1") or self.base_url.endswith("/api/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def get_action(self, goal, page_content, history):
        return self.sample_actions(goal, page_content, history, num_samples=1)[0]

    def sample_actions(self, goal, page_content, history, num_samples=1, temperature=None):
        messages = build_messages(goal, page_content, history, self.system_prompt)
        return self.sample_messages(messages, num_samples=num_samples, temperature=temperature)

    def sample_messages(self, messages, num_samples=1, temperature=None, max_tokens=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/webagent-suite",
            "X-Title": "WebAgent Dynamic Suite V2",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else float(temperature),
            "max_tokens": self.max_tokens if max_tokens is None else int(max_tokens),
        }
        if self.disable_thinking:
            payload["thinking"] = {"type": "disabled"}

        outputs = []
        target = max(1, int(num_samples or 1))
        for _ in range(target):
            outputs.append(self._single_completion(payload, headers))
        return outputs

    def _single_completion(self, payload, headers):
        local_payload = dict(payload)
        for attempt in range(3):
            try:
                if self.min_request_interval_sec > 0:
                    elapsed = time.time() - self._last_request_ts
                    if elapsed < self.min_request_interval_sec:
                        time.sleep(self.min_request_interval_sec - elapsed)
                response = requests.post(
                    self._chat_completions_url(),
                    headers=headers,
                    json=local_payload,
                    timeout=45,
                )
                self._last_request_ts = time.time()
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 15 + random.random() * 5
                    print(f"⚠️ 429 Rate Limit. Backing off for {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                response.raise_for_status()
                result = response.json()
                choice = result["choices"][0]
                message = choice.get("message", {}) or {}
                content = (message.get("content") or "").strip()
                reasoning = (message.get("reasoning_content") or "").strip()
                finish_reason = str(choice.get("finish_reason", "") or "").strip().lower()
                if content:
                    return content
                if reasoning and finish_reason == "length" and local_payload["max_tokens"] < 1024:
                    local_payload["max_tokens"] = max(int(local_payload["max_tokens"]) * 2, 768)
                    print(
                        f"⚠️ Empty content with reasoning-only response. "
                        f"Retrying with max_tokens={local_payload['max_tokens']}..."
                    )
                    continue
                return content
            except Exception as e:
                print(f"  ❌ API Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(5)

        return "ERROR(TimeoutOrLimit)"


class LocalHFClient:
    backend_name = "hf_local"

    def __init__(self):
        self.model = os.environ.get("AGENT_MODEL") or ""
        if not self.model:
            raise RuntimeError("AGENT_MODEL is required when AGENT_BACKEND=hf_local")
        self.adapter = (os.environ.get("AGENT_ADAPTER") or "").strip()

        raw_max_tokens = os.environ.get("AGENT_MAX_TOKENS")
        self.max_new_tokens = max(32, int(raw_max_tokens)) if raw_max_tokens else 80
        self.temperature = float(os.environ.get("AGENT_TEMPERATURE", "0.0"))
        self.device_map = os.environ.get("AGENT_HF_DEVICE_MAP", "auto")
        self.trust_remote_code = (os.environ.get("AGENT_HF_TRUST_REMOTE_CODE", "true").strip().lower() == "true")
        raw_use_chat_template = os.environ.get("AGENT_HF_USE_CHAT_TEMPLATE")
        if raw_use_chat_template is None:
            self.use_chat_template = _prompt_profile() not in {"webrl", "rl", "webarena_rl"}
        else:
            self.use_chat_template = raw_use_chat_template.strip().lower() == "true"
        raw_disable_thinking = os.environ.get("AGENT_DISABLE_THINKING")
        if raw_disable_thinking is None:
            self.disable_thinking = "qwen3" in self.model.lower()
        else:
            self.disable_thinking = raw_disable_thinking.strip().lower() == "true"
        self.system_prompt = _build_system_prompt()
        self._load_model()
        print(
            f"🚀 Client initialized | backend: {self.backend_name} | "
            f"model: {self.model} | adapter: {self.adapter or '<none>'} | "
            f"max_tokens: {self.max_new_tokens} | "
            f"use_chat_template: {self.use_chat_template} | "
            f"disable_thinking: {self.disable_thinking}"
        )

    def _load_model(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "hf_local backend requires torch and transformers. "
                "Install them before running local RL checkpoints."
            ) from exc

        self.torch = torch
        if self.adapter:
            adapter_path = Path(self.adapter)
            if not adapter_path.exists():
                raise RuntimeError(f"AGENT_ADAPTER does not exist: {self.adapter}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model,
            trust_remote_code=self.trust_remote_code,
        )
        model_kwargs = {
            "trust_remote_code": self.trust_remote_code,
        }
        dtype_name = (os.environ.get("AGENT_HF_DTYPE") or "auto").strip().lower()
        if dtype_name == "auto" and torch.cuda.is_available():
            model_kwargs["torch_dtype"] = getattr(torch, "bfloat16", torch.float16)
        elif dtype_name != "auto":
            dtype = getattr(torch, dtype_name, None)
            if dtype is not None:
                model_kwargs["torch_dtype"] = dtype
        if self.device_map:
            model_kwargs["device_map"] = self.device_map

        self.model_obj = AutoModelForCausalLM.from_pretrained(self.model, **model_kwargs)
        if self.adapter:
            try:
                from peft import PeftModel
            except ImportError as exc:
                raise RuntimeError(
                    "AGENT_ADAPTER requires peft to be installed in the current environment."
                ) from exc
            self.model_obj = PeftModel.from_pretrained(self.model_obj, self.adapter)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

    def _prepare_inputs(self, prompt: str):
        encoded = self.tokenizer(prompt, return_tensors="pt")
        target_device = getattr(self.model_obj, "device", None)
        if target_device is not None:
            try:
                encoded = {k: v.to(target_device) for k, v in encoded.items()}
            except Exception:
                pass
        return encoded

    def _render_prompt(self, messages: List[Dict[str, str]]) -> str:
        if self.use_chat_template and hasattr(self.tokenizer, "apply_chat_template"):
            kwargs = {
                "tokenize": False,
                "add_generation_prompt": True,
            }
            if self.disable_thinking:
                kwargs["enable_thinking"] = False
            try:
                return self.tokenizer.apply_chat_template(messages, **kwargs)
            except TypeError:
                kwargs.pop("enable_thinking", None)
                try:
                    return self.tokenizer.apply_chat_template(messages, **kwargs)
                except Exception:
                    pass
            except Exception:
                pass
        return _render_plain_prompt(messages)

    def get_action(self, goal, page_content, history):
        return self.sample_actions(goal, page_content, history, num_samples=1)[0]

    def sample_actions(self, goal, page_content, history, num_samples=1, temperature=None):
        messages = build_messages(goal, page_content, history, self.system_prompt)
        return self.sample_messages(messages, num_samples=num_samples, temperature=temperature)

    def sample_messages(self, messages, num_samples=1, temperature=None, max_tokens=None):
        prompt = self._render_prompt(messages)
        return self._sample_from_prompt(
            prompt,
            messages,
            num_samples=num_samples,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _sample_from_prompt(self, prompt, messages, num_samples=1, temperature=None, max_tokens=None):
        sample_temperature = self.temperature if temperature is None else float(temperature)
        inputs = self._prepare_inputs(prompt)
        input_len = inputs["input_ids"].shape[1]
        do_sample = sample_temperature > 0
        effective_max_tokens = self.max_new_tokens if max_tokens is None else max(1, int(max_tokens))
        with self.torch.no_grad():
            outputs = self.model_obj.generate(
                **inputs,
                max_new_tokens=effective_max_tokens,
                do_sample=do_sample,
                temperature=max(sample_temperature, 1e-5) if do_sample else None,
                num_return_sequences=max(1, int(num_samples or 1)) if do_sample else 1,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
        texts = []
        for row in outputs:
            generated = row[input_len:]
            text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
            if self.disable_thinking:
                text = _strip_thinking_block(text)
            texts.append(text)

        if self.use_chat_template and any(text in {"()", "[]", ""} for text in texts):
            fallback_prompt = _render_plain_prompt(messages)
            fallback_inputs = self._prepare_inputs(fallback_prompt)
            fallback_input_len = fallback_inputs["input_ids"].shape[1]
            with self.torch.no_grad():
                outputs = self.model_obj.generate(
                    **fallback_inputs,
                    max_new_tokens=effective_max_tokens,
                    do_sample=do_sample,
                    temperature=max(sample_temperature, 1e-5) if do_sample else None,
                    num_return_sequences=max(1, int(num_samples or 1)) if do_sample else 1,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            texts = []
            for row in outputs:
                generated = row[fallback_input_len:]
                text = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
                if self.disable_thinking:
                    text = _strip_thinking_block(text)
                texts.append(text)
        if not texts:
            return [""]
        return texts


def build_client():
    backend = (os.environ.get("AGENT_BACKEND") or "openai_compatible").strip().lower()
    if backend in {"hf_local", "transformers", "local_hf"}:
        return LocalHFClient()
    return OpenAICompatibleClient()


class GLMClient(OpenAICompatibleClient):
    pass
