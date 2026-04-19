"""
Sub-Agent Manager: Spawn, monitor, and coordinate child agents.
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

import aiohttp
import yaml

logger = logging.getLogger("Nova-OS")


class SubAgentTask:
    """Represents a sub-agent task."""
    
    def __init__(self, task_id: str, description: str, agent_type: str, 
                 parameters: Dict[str, Any]):
        self.id = task_id
        self.description = description
        self.agent_type = agent_type  # 'code', 'research', 'file_ops', 'shell', 'skill'
        self.parameters = parameters
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None
        self.pid = None


class SubAgentManager:
    """Manages sub-agents and parallel task execution."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tasks: Dict[str, SubAgentTask] = {}
        self.max_parallel = config.get('max_parallel', 5)
        self.working_dir = Path(config.get('working_dir', '~/.nova-os/subagents')).expanduser()
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        # ClawHub config
        self.clawhub_enabled = config.get('clawhub', {}).get('enabled', True)
        self.clawhub_url = config.get('clawhub', {}).get('url', 'https://clawhub.ai')
        
    async def spawn(self, description: str, agent_type: str, 
                   parameters: Dict[str, Any]) -> str:
        """Spawn a new sub-agent task."""
        task_id = str(uuid.uuid4())[:8]
        task = SubAgentTask(task_id, description, agent_type, parameters)
        self.tasks[task_id] = task
        
        logger.info(f"Spawning sub-agent {task_id}: {description}")
        
        # Start based on agent type
        if agent_type == "code":
            asyncio.create_task(self._run_code_agent(task))
        elif agent_type == "research":
            asyncio.create_task(self._run_research_agent(task))
        elif agent_type == "file_ops":
            asyncio.create_task(self._run_file_agent(task))
        elif agent_type == "shell":
            asyncio.create_task(self._run_shell_agent(task))
        elif agent_type == "skill":
            asyncio.create_task(self._run_skill_install(task))
        elif agent_type == "custom":
            asyncio.create_task(self._run_custom_agent(task))
        else:
            task.status = "failed"
            task.error = f"Unknown agent type: {agent_type}"
        
        return task_id
    
    async def _run_code_agent(self, task: SubAgentTask):
        """Run code generation sub-agent."""
        task.status = "running"
        
        try:
            prompt = task.parameters.get('prompt', '')
            language = task.parameters.get('language', 'python')
            
            # Create temp file for the code
            temp_file = self.working_dir / f"{task.id}_code.{language}"
            
            # Run code generation via AI
            from .ai_engine import AIEngine
            ai_config = self.config.get('model', {})
            ai = AIEngine(ai_config, None)  # No memory for sub-agents
            
            code = await ai.generate_code(prompt, language)
            
            # Save to file
            temp_file.write_text(code)
            
            task.result = {
                "code": code,
                "file": str(temp_file),
                "language": language
            }
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            logger.error(f"Code agent {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
    
    async def _run_research_agent(self, task: SubAgentTask):
        """Run research sub-agent (web search + analysis)."""
        task.status = "running"
        
        try:
            query = task.parameters.get('query', '')
            sources = task.parameters.get('sources', 5)
            
            # Use Tavily if available
            tavily_key = self.config.get('tavily_api_key')
            
            if tavily_key:
                results = await self._tavily_search(query, sources, tavily_key)
            else:
                # Fallback to simple web fetch
                results = await self._simple_search(query)
            
            task.result = {
                "query": query,
                "results": results,
                "summary": self._summarize_results(results)
            }
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            logger.error(f"Research agent {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
    
    async def _run_file_agent(self, task: SubAgentTask):
        """Run file operations sub-agent."""
        task.status = "running"
        
        try:
            operation = task.parameters.get('operation')
            source = task.parameters.get('source')
            destination = task.parameters.get('destination')
            
            if operation == 'copy':
                subprocess.run(['cp', '-r', source, destination], check=True)
            elif operation == 'move':
                subprocess.run(['mv', source, destination], check=True)
            elif operation == 'delete':
                subprocess.run(['rm', '-rf', source], check=True)
            elif operation == 'list':
                result = subprocess.run(['ls', '-la', source], 
                                      capture_output=True, text=True)
                task.result = {"listing": result.stdout}
            
            if operation != 'list':
                task.result = {"success": True, "operation": operation}
            
            task.status = "completed"
            task.completed_at = datetime.now()
            
        except Exception as e:
            logger.error(f"File agent {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
    
    async def _run_shell_agent(self, task: SubAgentTask):
        """Run shell command sub-agent."""
        task.status = "running"
        
        try:
            command = task.parameters.get('command')
            timeout = task.parameters.get('timeout', 60)
            
            # Security check
            forbidden = ['rm -rf /', 'mkfs', ':(){ :|:& };:']
            if any(f in command for f in forbidden):
                raise ValueError("Forbidden command detected")
            
            # Run in subprocess
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            
            task.result = {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": proc.returncode
            }
            task.status = "completed"
            task.completed_at = datetime.now()
            task.pid = proc.pid
            
        except asyncio.TimeoutError:
            task.status = "failed"
            task.error = "Command timed out"
        except Exception as e:
            logger.error(f"Shell agent {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
    
    async def _run_skill_install(self, task: SubAgentTask):
        """Install ClawHub skill via sub-agent."""
        task.status = "running"
        
        try:
            skill_name = task.parameters.get('skill_name')
            
            # Check if ClawHub CLI is available
            clawhub_path = Path.home() / '.openclaw' / 'openclaw.mjs'
            
            if not clawhub_path.exists():
                # Try global install
                result = subprocess.run(
                    ['which', 'openclaw'],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise RuntimeError("ClawHub not installed. Run: npm install -g openclaw")
                clawhub_cmd = 'openclaw'
            else:
                clawhub_cmd = f'node {clawhub_path}'
            
            # Install skill
            install_cmd = f'{clawhub_cmd} skills install {skill_name}'
            
            proc = await asyncio.create_subprocess_shell(
                install_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            
            # Check if installed
            skill_path = Path.home() / '.openclaw' / 'workspace' / 'skills' / skill_name
            installed = skill_path.exists()
            
            task.result = {
                "skill": skill_name,
                "installed": installed,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "skill_path": str(skill_path) if installed else None
            }
            task.status = "completed" if installed else "failed"
            task.completed_at = datetime.now()
            
            if not installed:
                task.error = stderr.decode() or "Installation failed"
            
        except Exception as e:
            logger.error(f"Skill install {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
    
    async def _run_custom_agent(self, task: SubAgentTask):
        """Run custom Python script as sub-agent."""
        task.status = "running"
        
        try:
            script = task.parameters.get('script')
            args = task.parameters.get('args', [])
            
            # Write script to temp file
            script_file = self.working_dir / f"{task.id}_custom.py"
            script_file.write_text(script)
            
            # Run script
            proc = await asyncio.create_subprocess_exec(
                'python3', str(script_file), *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=300
            )
            
            task.result = {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": proc.returncode
            }
            task.status = "completed"
            task.completed_at = datetime.now()
            
            # Cleanup
            script_file.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Custom agent {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
    
    async def _tavily_search(self, query: str, sources: int, api_key: str) -> List[Dict]:
        """Search using Tavily API."""
        url = "https://api.tavily.com/search"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "query": query,
            "search_depth": "advanced",
            "include_answer": True,
            "max_results": sources
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                return data.get('results', [])
    
    async def _simple_search(self, query: str) -> List[Dict]:
        """Fallback simple search (DuckDuckGo or similar)."""
        # Simplified - just return placeholder
        return [{"title": "Search not configured", "url": "", "content": "Please add Tavily API key for search"}]
    
    def _summarize_results(self, results: List[Dict]) -> str:
        """Summarize search results."""
        if not results:
            return "No results found"
        
        summary = []
        for i, r in enumerate(results[:3], 1):
            title = r.get('title', 'No title')
            content = r.get('content', '')[:200]
            summary.append(f"{i}. {title}: {content}...")
        
        return "\n".join(summary)
    
    def get_task(self, task_id: str) -> Optional[SubAgentTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: Optional[str] = None) -> List[SubAgentTask]:
        """List all tasks, optionally filtered by status."""
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sub-agent statistics."""
        total = len(self.tasks)
        pending = len([t for t in self.tasks.values() if t.status == "pending"])
        running = len([t for t in self.tasks.values() if t.status == "running"])
        completed = len([t for t in self.tasks.values() if t.status == "completed"])
        failed = len([t for t in self.tasks.values() if t.status == "failed"])
        
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "max_parallel": self.max_parallel
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        task = self.tasks.get(task_id)
        if not task or task.status != "running":
            return False
        
        # Note: Python subprocess cancellation is limited
        # We'd need to track PIDs and send signals
        task.status = "cancelled"
        task.completed_at = datetime.now()
        return True
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove old completed tasks."""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        to_remove = [
            tid for tid, t in self.tasks.items()
            if t.completed_at and t.completed_at.timestamp() < cutoff
        ]
        for tid in to_remove:
            del self.tasks[tid]