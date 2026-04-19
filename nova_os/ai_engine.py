"""
AI Engine: Handles Ollama (primary) and Cloud API (fallback) communication.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from ollama import AsyncClient as OllamaClient

logger = logging.getLogger("Nova-OS")

class AIEngine:
    """AI communication layer with local Ollama + cloud fallback."""
    
    def __init__(self, config: Dict[str, Any], memory_manager):
        self.config = config
        self.memory = memory_manager
        
        # Ollama config (primary)
        self.ollama_url = config.get('ollama_base_url', 'http://localhost:11434')
        self.ollama_model = config.get('model', 'llama3.2:3b')
        self.ollama = OllamaClient(host=self.ollama_url)
        
        # Cloud fallback config
        self.cloud_provider = config.get('provider', 'ollama')
        self.cloud_model = config.get('cloud_model')
        self.api_key = config.get('api_key')
        
        self.system_prompt = self._load_system_prompt()
        
    def _load_system_prompt(self) -> str:
        """Load system personality."""
        return """You are Nova-OS, a helpful personal AI assistant.
You are running locally on the user's machine via Ollama.

Your capabilities:
- Answer questions and have conversations
- Help with coding, writing, analysis
- Remember context from previous messages
- Execute system commands (when user asks)
- Stay helpful, friendly, and concise

Always respond in the user's language.
Be direct and practical."""
    
    async def chat(self, user_id: int, message: str) -> str:
        """Get AI response for user message."""
        # Build conversation context
        history = self.memory.get_thread(user_id, limit=10)
        
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add history
        for h in history:
            messages.append({"role": "user", "content": h['user']})
            if h.get('assistant'):
                messages.append({"role": "assistant", "content": h['assistant']})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # Try Ollama first
        try:
            response = await self._ollama_chat(messages)
        except Exception as e:
            logger.warning(f"Ollama failed: {e}. Trying cloud fallback...")
            response = await self._cloud_chat(messages)
        
        # Save to memory
        self.memory.add_exchange(user_id, message, response)
        
        return response
    
    async def _ollama_chat(self, messages: List[Dict]) -> str:
        """Chat via Ollama (local)."""
        response = await self.ollama.chat(
            model=self.ollama_model,
            messages=messages,
            options={
                'temperature': 0.7,
                'num_predict': 1024,
            }
        )
        return response['message']['content']
    
    async def _cloud_chat(self, messages: List[Dict]) -> str:
        """Chat via cloud API (fallback)."""
        if not self.api_key:
            return "❌ Ollama is offline and no cloud API key configured."
        
        if self.cloud_provider == 'openai':
            return await self._openai_chat(messages)
        elif self.cloud_provider == 'google':
            return await self._google_chat(messages)
        else:
            return "❌ Unsupported cloud provider."
    
    async def _openai_chat(self, messages: List[Dict]) -> str:
        """OpenAI API fallback."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.cloud_model or "gpt-3.5-turbo",
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=30
            )
            data = response.json()
            return data['choices'][0]['message']['content']
    
    async def _google_chat(self, messages: List[Dict]) -> str:
        """Google Gemini API fallback."""
        async with httpx.AsyncClient() as client:
            # Combine messages for Gemini
            prompt = "\n".join([m['content'] for m in messages])
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.cloud_model or 'gemini-pro'}:generateContent",
                headers={"x-goog-api-key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30
            )
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
    
    async def generate_code(self, prompt: str, language: str = "python") -> str:
        """Generate code with specific formatting."""
        code_prompt = f"""Generate {language} code for the following:
{prompt}

Requirements:
- Include comments
- Follow best practices
- Make it complete and runnable

Return ONLY the code, no markdown code blocks."""
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": code_prompt}
        ]
        
        try:
            return await self._ollama_chat(messages)
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return f"❌ Failed to generate code: {e}"