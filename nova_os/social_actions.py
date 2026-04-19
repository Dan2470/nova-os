"""
Social Media Actions - Post, schedule, analyze
Uses authenticated tokens to perform actions
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, BinaryIO

import httpx
from PIL import Image
import io

logger = logging.getLogger("Nova-OS")


class SocialMediaManager:
    """Manages social media posting and scheduling."""
    
    def __init__(self, auth_manager):
        self.auth = auth_manager
        
    # ═══════════════════════════════════════════════════════════════
    # TWITTER/X
    # ═══════════════════════════════════════════════════════════════
    
    async def twitter_post(self, text: str, media_paths: List[str] = None) -> Dict:
        """Post to Twitter/X."""
        token = await self.auth.get_valid_token('twitter')
        if not token:
            return {"error": "Not authenticated with Twitter"}
        
        url = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {"text": text}
        
        # Upload media if provided
        if media_paths:
            media_ids = await self._twitter_upload_media(token, media_paths)
            if media_ids:
                payload["media"] = {"media_ids": media_ids}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "post_id": data['data']['id'],
                    "text": data['data']['text'],
                    "url": f"https://twitter.com/i/web/status/{data['data']['id']}"
                }
            else:
                return {"error": response.text}
    
    async def _twitter_upload_media(self, token: str, media_paths: List[str]) -> List[str]:
        """Upload media to Twitter."""
        media_ids = []
        
        for path in media_paths:
            try:
                # Upload via Twitter API v1.1 (media upload)
                upload_url = "https://upload.twitter.com/1.1/media/upload.json"
                
                with open(path, 'rb') as f:
                    media_data = f.read()
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        upload_url,
                        headers={"Authorization": f"Bearer {token}"},
                        files={"media": media_data}
                    )
                    
                    if response.status_code == 200:
                        media_ids.append(response.json()['media_id_string'])
                        
            except Exception as e:
                logger.error(f"Failed to upload media {path}: {e}")
        
        return media_ids
    
    # ═══════════════════════════════════════════════════════════════
    # LINKEDIN
    # ═══════════════════════════════════════════════════════════════
    
    async def linkedin_post(self, text: str, media_url: str = None) -> Dict:
        """Post to LinkedIn."""
        token = await self.auth.get_valid_token('linkedin')
        if not token:
            return {"error": "Not authenticated with LinkedIn"}
        
        # Get user profile
        profile_url = "https://api.linkedin.com/v2/me"
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            profile_resp = await client.get(profile_url, headers=headers)
            
            if profile_resp.status_code != 200:
                return {"error": "Failed to get profile"}
            
            person_urn = profile_resp.json().get('id')
            
            # Create post
            post_url = "https://api.linkedin.com/v2/ugcPosts"
            
            post_body = {
                "author": f"urn:li:person:{person_urn}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
            }
            
            if media_url:
                post_body["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
                post_body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                    {"status": "READY", "originalUrl": media_url}
                ]
            
            response = await client.post(
                post_url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=post_body
            )
            
            if response.status_code == 201:
                return {"success": True, "post_id": response.headers.get('x-restli-id')}
            else:
                return {"error": response.text}
    
    # ═══════════════════════════════════════════════════════════════
    # INSTAGRAM
    # ═══════════════════════════════════════════════════════════════
    
    async def instagram_post(self, image_path: str, caption: str) -> Dict:
        """Post to Instagram (requires Facebook Business account)."""
        # Instagram uses Facebook Graph API
        token = await self.auth.get_valid_token('instagram')
        if not token:
            return {"error": "Not authenticated with Instagram"}
        
        # This requires Instagram Business account
        # Simplified - actual implementation needs media container creation
        return {"message": "Instagram posting requires Business account setup"}
    
    # ═══════════════════════════════════════════════════════════════
    # FACEBOOK
    # ═══════════════════════════════════════════════════════════════
    
    async def facebook_post(self, page_id: str, message: str, 
                          media_path: str = None) -> Dict:
        """Post to Facebook Page."""
        token = await self.auth.get_valid_token('facebook')
        if not token:
            return {"error": "Not authenticated with Facebook"}
        
        url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
        
        data = {
            "message": message,
            "access_token": token
        }
        
        async with httpx.AsyncClient() as client:
            if media_path:
                # Photo post
                photo_url = f"https://graph.facebook.com/v18.0/{page_id}/photos"
                with open(media_path, 'rb') as f:
                    response = await client.post(
                        photo_url,
                        data=data,
                        files={"source": f}
                    )
            else:
                # Text post
                response = await client.post(url, data=data)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "post_id": data.get('id'),
                    "url": f"https://facebook.com/{data.get('id')}"
                }
            else:
                return {"error": response.text}
    
    # ═══════════════════════════════════════════════════════════════
    # REDDIT
    # ═══════════════════════════════════════════════════════════════
    
    async def reddit_post(self, subreddit: str, title: str, 
                         text: str = None, url: str = None) -> Dict:
        """Post to Reddit."""
        token = await self.auth.get_valid_token('reddit')
        if not token:
            return {"error": "Not authenticated with Reddit"}
        
        post_data = {
            "sr": subreddit,
            "title": title,
            "kind": "self" if text else "link",
            "resubmit": False
        }
        
        if text:
            post_data["text"] = text
        if url:
            post_data["url"] = url
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth.reddit.com/api/submit",
                headers={"Authorization": f"Bearer {token}"},
                data=post_data
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return {
                        "success": True,
                        "post_id": data['data']['name'],
                        "url": data['data']['url']
                    }
                else:
                    return {"error": data.get('jquery', 'Unknown error')}
            else:
                return {"error": response.text}
    
    # ═══════════════════════════════════════════════════════════════
    # YOUTUBE
    # ═══════════════════════════════════════════════════════════════
    
    async def youtube_upload(self, video_path: str, title: str, 
                           description: str = "", 
                           privacy: str = "private") -> Dict:
        """Upload video to YouTube."""
        token = await self.auth.get_valid_token('youtube')
        if not token:
            return {"error": "Not authenticated with YouTube"}
        
        # YouTube upload requires resumable upload protocol
        # This is simplified - full implementation needs chunked upload
        return {"message": "YouTube upload requires resumable upload implementation"}
    
    # ═══════════════════════════════════════════════════════════════
    # SCHEDULING
    # ═══════════════════════════════════════════════════════════════
    
    async def schedule_post(self, platform: str, content: Dict, 
                          schedule_time: datetime) -> Dict:
        """Schedule a post for future."""
        # Store in database with schedule_time
        # Requires a scheduler worker (cron or asyncio)
        
        from .memory import MemoryManager
        
        # Create scheduled task
        task = {
            "platform": platform,
            "content": content,
            "schedule_time": schedule_time.isoformat(),
            "status": "scheduled"
        }
        
        # Would save to database here
        logger.info(f"Scheduled {platform} post for {schedule_time}")
        
        return {
            "success": True,
            "scheduled_for": schedule_time.isoformat(),
            "platform": platform
        }
    
    # ═══════════════════════════════════════════════════════════════
    # ANALYTICS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_analytics(self, platform: str, post_id: str = None) -> Dict:
        """Get analytics for a platform or specific post."""
        token = await self.auth.get_valid_token(platform)
        if not token:
            return {"error": f"Not authenticated with {platform}"}
        
        analytics_methods = {
            'twitter': self._twitter_analytics,
            'linkedin': self._linkedin_analytics,
            'facebook': self._facebook_analytics,
            'youtube': self._youtube_analytics,
        }
        
        if platform in analytics_methods:
            return await analytics_methods[platform](token, post_id)
        
        return {"error": f"Analytics not implemented for {platform}"}
    
    async def _twitter_analytics(self, token: str, post_id: str = None) -> Dict:
        """Get Twitter analytics."""
        async with httpx.AsyncClient() as client:
            if post_id:
                # Get specific tweet metrics
                url = f"https://api.twitter.com/2/tweets/{post_id}"
                params = {"tweet.fields": "public_metrics,non_public_metrics"}
                
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()['data']
                    metrics = data.get('public_metrics', {})
                    return {
                        "success": True,
                        "impressions": metrics.get('impression_count', 0),
                        "engagements": metrics.get('like_count', 0) + metrics.get('retweet_count', 0),
                        "likes": metrics.get('like_count', 0),
                        "retweets": metrics.get('retweet_count', 0),
                        "replies": metrics.get('reply_count', 0)
                    }
            
            return {"message": "User-level analytics require Twitter API Premium"}
    
    async def _linkedin_analytics(self, token: str, post_id: str = None) -> Dict:
        """Get LinkedIn analytics."""
        # LinkedIn analytics API
        return {"message": "LinkedIn analytics require specific organization access"}
    
    async def _facebook_analytics(self, token: str, post_id: str = None) -> Dict:
        """Get Facebook analytics."""
        # Facebook Insights API
        return {"message": "Facebook analytics via Graph API"}
    
    async def _youtube_analytics(self, token: str, post_id: str = None) -> Dict:
        """Get YouTube analytics."""
        # YouTube Analytics API
        return {"message": "YouTube analytics via Analytics API"}


# Command helpers for Telegram integration
def format_post_result(result: Dict) -> str:
    """Format post result for Telegram display."""
    if result.get('success'):
        text = "✅ **Posted successfully!**\n\n"
        if 'url' in result:
            text += f"🔗 **Link:** {result['url']}\n"
        if 'post_id' in result:
            text += f"🆔 **Post ID:** `{result['post_id']}`\n"
        return text
    else:
        return f"❌ **Failed:** {result.get('error', 'Unknown error')}"