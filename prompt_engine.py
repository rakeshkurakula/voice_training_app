"""LLM abstraction with budget & retry control."""
from __future__ import annotations
import os, asyncio, httpx, backoff, yaml
from typing import Literal, Dict
from pathlib import Path

class PromptEngine:
    def __init__(self, config_path: str = "config.yaml", timeout: int = 20):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.provider = self.config["llm"]["provider"]
        self.timeout = timeout
        
        # Load environment variables
        self._load_env_vars()
        
        # Initialize API clients
        self._init_clients()

    def _load_env_vars(self):
        """Load API keys from environment variables."""
        # Load from .env file if it exists
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        
        # Set API keys from environment
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_org_id = os.getenv("OPENAI_ORG_ID")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # Validate required API keys
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")
        elif self.provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for Gemini provider")

    def _init_clients(self):
        """Initialize API clients based on provider."""
        if self.provider == "openai":
            import openai
            openai.api_key = self.openai_api_key
            if self.openai_org_id:
                openai.organization = self.openai_org_id
            
            # Set custom base URL if configured
            base_url = self.config["llm"]["openai"].get("base_url")
            if base_url and base_url != "https://api.openai.com/v1":
                openai.base_url = base_url
                
        elif self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_api_key)
            
            # Set custom base URL if configured
            base_url = self.config["llm"]["gemini"].get("base_url")
            if base_url:
                genai.base_url = base_url

    @backoff.on_exception(backoff.expo, (httpx.HTTPError, TimeoutError), max_tries=3)
    async def __call__(self, prompt: str, **kw) -> str:
        if self.provider == "openai":
            import openai, tiktoken
            
            # Get model from config
            model = kw.get("model") or self.config["llm"]["model"]
            max_tokens = kw.get("max_tokens") or self.config["llm"]["max_tokens"]
            
            enc = tiktoken.encoding_for_model(model)
            if len(enc.encode(prompt)) > max_tokens:
                prompt = prompt[-2048:]   # truncate oldest tokens
                
            resp = await openai.ChatCompletion.acreate(
                model=model, 
                messages=[{"role":"user","content":prompt}],
                max_tokens=max_tokens, 
                timeout=self.timeout
            )
            return resp.choices[0].message.content
            
        else:  # gemini
            import google.generativeai as genai
            
            # Get model from config
            model_name = kw.get("model") or self.config["llm"]["gemini"]["model"]
            max_tokens = kw.get("max_tokens") or self.config["llm"]["max_tokens"]
            
            model = genai.GenerativeModel(model_name)
            
            # Configure safety settings if specified
            safety_settings = self.config["llm"]["gemini"].get("safety_settings")
            if safety_settings and safety_settings != "default":
                # You can customize safety settings here if needed
                pass
                
            resp = await asyncio.to_thread(
                model.generate_content, 
                prompt,
                generation_config={"max_output_tokens": max_tokens}
            )
            return resp.text
