"""
Social Media Authentication Manager
Handles OAuth flows for Twitter/X, LinkedIn, Instagram, Facebook, etc.
"""
import asyncio
import hashlib
import json
import logging
import secrets
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable
from urllib.parse import parse_qs, urlparse

import httpx
from aiohttp import web

logger = logging.getLogger("Nova-OS")


class SocialAuthManager:
    """Manages OAuth authentication for social media platforms."""
    
    PLATFORMS = {
        'twitter': {
            'name': 'Twitter/X',
            'auth_url': 'https://twitter.com/i/oauth2/authorize',
            'token_url': 'https://api.twitter.com/2/oauth2/token',
            'scopes': ['tweet.read', 'tweet.write', 'users.read', 'offline.access'],
            'pkce': True,
        },
        'linkedin': {
            'name': 'LinkedIn',
            'auth_url': 'https://www.linkedin.com/oauth/v2/authorization',
            'token_url': 'https://www.linkedin.com/oauth/v2/accessToken',
            'scopes': ['r_liteprofile', 'r_emailaddress', 'w_member_social'],
            'pkce': False,
        },
        'instagram': {
            'name': 'Instagram',
            'auth_url': 'https://api.instagram.com/oauth/authorize',
            'token_url': 'https://api.instagram.com/oauth/access_token',
            'scopes': ['instagram_basic', 'instagram_content_publish'],
            'pkce': False,
        },
        'facebook': {
            'name': 'Facebook',
            'auth_url': 'https://www.facebook.com/v18.0/dialog/oauth',
            'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
            'scopes': ['email', 'public_profile', 'pages_read_engagement', 'pages_manage_posts'],
            'pkce': False,
        },
        'reddit': {
            'name': 'Reddit',
            'auth_url': 'https://www.reddit.com/api/v1/authorize',
            'token_url': 'https://www.reddit.com/api/v1/access_token',
            'scopes': ['read', 'submit', 'identity'],
            'pkce': True,
        },
        'youtube': {
            'name': 'YouTube',
            'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
            'token_url': 'https://oauth2.googleapis.com/token',
            'scopes': [
                'https://www.googleapis.com/auth/youtube.readonly',
                'https://www.googleapis.com/auth/youtube.upload'
            ],
            'pkce': True,
        },
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.credentials_path = Path(config.get('credentials_file', 
                                               '~/.config/nova-os/social_credentials.json')).expanduser()
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.credentials = self._load_credentials()
        self.pending_auth = {}  # Store pending auth states
        
    def _load_credentials(self) -> Dict:
        """Load stored credentials."""
        if self.credentials_path.exists():
            try:
                with open(self.credentials_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load credentials: {e}")
        return {}
    
    def _save_credentials(self):
        """Save credentials to file."""
        with open(self.credentials_path, 'w') as f:
            json.dump(self.credentials, f, indent=2)
    
    async def start_auth(self, platform: str, credentials: Dict) -> str:
        """Start OAuth flow for a platform.
        
        Args:
            platform: Platform name (twitter, linkedin, etc.)
            credentials: Dict with client_id, client_secret, redirect_uri
            
        Returns:
            Authorization URL for user to visit
        """
        if platform not in self.PLATFORMS:
            raise ValueError(f"Unknown platform: {platform}. "
                           f"Supported: {', '.join(self.PLATFORMS.keys())}")
        
        platform_config = self.PLATFORMS[platform]
        
        # Generate state and PKCE
        state = secrets.token_urlsafe(32)
        code_verifier = None
        
        if platform_config['pkce']:
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = self._base64_urlencode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
        
        # Store pending auth
        self.pending_auth[state] = {
            'platform': platform,
            'credentials': credentials,
            'code_verifier': code_verifier,
            'timestamp': datetime.now(),
        }
        
        # Build auth URL
        params = {
            'client_id': credentials['client_id'],
            'redirect_uri': credentials.get('redirect_uri', 'http://localhost:8080/callback'),
            'response_type': 'code',
            'state': state,
            'scope': ' '.join(platform_config['scopes']),
        }
        
        if platform_config['pkce']:
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = 'S256'
        
        # Build URL
        import urllib.parse
        auth_url = f"{platform_config['auth_url']}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"Started auth for {platform}. URL: {auth_url[:100]}...")
        
        return auth_url
    
    async def handle_callback(self, callback_url: str) -> Dict:
        """Handle OAuth callback.
        
        Args:
            callback_url: Full callback URL including code and state
            
        Returns:
            Token info dict
        """
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        
        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]
        error = params.get('error', [None])[0]
        
        if error:
            raise RuntimeError(f"OAuth error: {error}")
        
        if not code or not state:
            raise ValueError("Missing code or state in callback")
        
        if state not in self.pending_auth:
            raise RuntimeError("Invalid or expired state")
        
        auth_info = self.pending_auth[state]
        platform = auth_info['platform']
        credentials = auth_info['credentials']
        code_verifier = auth_info['code_verifier']
        
        # Exchange code for token
        token_data = await self._exchange_code(
            platform, code, credentials, code_verifier
        )
        
        # Store credentials
        self.credentials[platform] = {
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'expires_at': (datetime.now() + 
                           timedelta(seconds=token_data.get('expires_in', 3600))
                           ).isoformat(),
            'token_type': token_data.get('token_type', 'Bearer'),
            'scope': token_data.get('scope', ''),
        }
        
        self._save_credentials()
        
        # Clean up pending auth
        del self.pending_auth[state]
        
        logger.info(f"Successfully authenticated {platform}")
        
        return self.credentials[platform]
    
    async def _exchange_code(self, platform: str, code: str, 
                            credentials: Dict, code_verifier: Optional[str]) -> Dict:
        """Exchange authorization code for access token."""
        platform_config = self.PLATFORMS[platform]
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': credentials.get('redirect_uri', 'http://localhost:8080/callback'),
            'client_id': credentials['client_id'],
        }
        
        if code_verifier:
            data['code_verifier'] = code_verifier
        
        # Some platforms require client_secret
        if 'client_secret' in credentials:
            data['client_secret'] = credentials['client_secret']
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        # Reddit requires basic auth header
        if platform == 'reddit':
            import base64
            auth_str = base64.b64encode(
                f"{credentials['client_id']}:{credentials['client_secret']}".encode()
            ).decode()
            headers['Authorization'] = f'Basic {auth_str}'
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                platform_config['token_url'],
                data=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    
    async def refresh_token(self, platform: str) -> Optional[Dict]:
        """Refresh access token using refresh token."""
        if platform not in self.credentials:
            return None
        
        creds = self.credentials[platform]
        refresh_token = creds.get('refresh_token')
        
        if not refresh_token:
            logger.warning(f"No refresh token for {platform}")
            return None
        
        platform_config = self.PLATFORMS[platform]
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                platform_config['token_url'],
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                self.credentials[platform].update({
                    'access_token': token_data.get('access_token'),
                    'expires_at': (datetime.now() + 
                                   timedelta(seconds=token_data.get('expires_in', 3600))
                                   ).isoformat(),
                })
                
                self._save_credentials()
                return self.credentials[platform]
            else:
                logger.error(f"Failed to refresh {platform} token: {response.text}")
                return None
    
    async def get_valid_token(self, platform: str) -> Optional[str]:
        """Get valid access token, refreshing if necessary."""
        if platform not in self.credentials:
            return None
        
        creds = self.credentials[platform]
        expires_at = datetime.fromisoformat(creds.get('expires_at', '2000-01-01'))
        
        # Refresh if expiring within 5 minutes
        if datetime.now() > expires_at - timedelta(minutes=5):
            refreshed = await self.refresh_token(platform)
            if refreshed:
                return refreshed.get('access_token')
            return None
        
        return creds.get('access_token')
    
    def is_authenticated(self, platform: str) -> bool:
        """Check if platform is authenticated."""
        return platform in self.credentials
    
    def list_authenticated(self) -> list:
        """List all authenticated platforms."""
        return list(self.credentials.keys())
    
    async def revoke(self, platform: str):
        """Revoke authentication for a platform."""
        if platform in self.credentials:
            # Try to revoke token with provider
            token = self.credentials[platform].get('access_token')
            if token:
                await self._revoke_token(platform, token)
            
            del self.credentials[platform]
            self._save_credentials()
            logger.info(f"Revoked {platform} authentication")
    
    async def _revoke_token(self, platform: str, token: str):
        """Revoke token with provider."""
        # Platform-specific revocation URLs
        revoke_urls = {
            'twitter': 'https://api.twitter.com/2/oauth2/revoke',
            'google': 'https://oauth2.googleapis.com/revoke',
        }
        
        if platform in revoke_urls:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        revoke_urls[platform],
                        data={'token': token}
                    )
            except Exception as e:
                logger.warning(f"Failed to revoke {platform} token: {e}")
    
    def get_auth_instructions(self, platform: str) -> str:
        """Get instructions for setting up OAuth app."""
        instructions = {
            'twitter': """**Twitter/X Setup:**
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a new app
3. Enable OAuth 2.0
4. Add redirect URI: http://localhost:8080/callback
5. Copy Client ID and Secret""",
            
            'linkedin': """**LinkedIn Setup:**
1. Go to https://www.linkedin.com/developers/apps
2. Create new app
3. Add OAuth 2.0 scopes
4. Set redirect URL: http://localhost:8080/callback
5. Get Client ID and Secret""",
            
            'instagram': """**Instagram Setup:**
1. Go to https://developers.facebook.com/apps
2. Create app → Consumer → Instagram
3. Add Instagram Basic Display
4. Set redirect URI
5. Get App ID and Secret""",
            
            'youtube': """**YouTube Setup:**
1. Go to https://console.cloud.google.com
2. Create project → APIs & Services
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Add redirect URI""",
        }
        
        return instructions.get(platform, f"Visit {platform} developer portal to create OAuth app.")


# Helper functions for subagent integration
async def social_auth_start(platform: str, client_id: str, client_secret: str = None) -> str:
    """Start social auth flow (for subagent use)."""
    auth_manager = SocialAuthManager({})
    
    credentials = {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'http://localhost:8080/callback',
    }
    
    auth_url = await auth_manager.start_auth(platform, credentials)
    
    return f"""**Authorization Required**

1. Visit this URL:
{auth_url}

2. Login and approve permissions

3. Copy the full callback URL and reply with:
`/auth_callback <paste_url>`
"""


async def social_auth_complete(callback_url: str) -> str:
    """Complete social auth flow."""
    auth_manager = SocialAuthManager({})
    
    try:
        token_info = await auth_manager.handle_callback(callback_url)
        return f"✅ Successfully authenticated! Token saved."
    except Exception as e:
        return f"❌ Authentication failed: {e}"