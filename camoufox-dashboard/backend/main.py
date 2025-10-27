from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import uuid
import asyncio
from datetime import datetime
import logging
from camoufox_manager import CamoufoxManager

# Ensure Windows event loop supports subprocesses (required by Playwright).
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        logging.getLogger(__name__).warning(
            "WindowsProactorEventLoopPolicy unavailable; Playwright may fail to launch."
        )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Camoufox Dashboard API", version="1.0.0")

# Data models
class ProfileCreate(BaseModel):
    name: str
    os: str
    timezone: str

class Profile(BaseModel):
    id: str
    name: str
    os: str
    timezone: str
    status: str = "inactive"
    created_at: str
    config: Optional[Dict[str, Any]] = None

class ProfileManager:
    def __init__(self):
        self.profiles_file = "profiles.json"
        self.camoufox_manager = CamoufoxManager()  # Enhanced Camoufox manager
        self.load_profiles()

    def load_profiles(self):
        """Load profiles from JSON file"""
        try:
            if os.path.exists(self.profiles_file):
                with open(self.profiles_file, 'r') as f:
                    data = json.load(f)
                    self.profiles = [Profile(**profile) for profile in data]
            else:
                self.profiles = []
        except Exception as e:
            logger.error(f"Error loading profiles: {e}")
            self.profiles = []

    def save_profiles(self):
        """Save profiles to JSON file"""
        try:
            with open(self.profiles_file, 'w') as f:
                json.dump([profile.dict() for profile in self.profiles], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving profiles: {e}")

    def create_profile(self, profile_data: ProfileCreate) -> Profile:
        """Create a new profile"""
        profile_id = str(uuid.uuid4())
        
        # Generate Camoufox configuration based on OS and timezone
        config = self.generate_camoufox_config(profile_data.os, profile_data.timezone)
        
        profile = Profile(
            id=profile_id,
            name=profile_data.name,
            os=profile_data.os,
            timezone=profile_data.timezone,
            status="inactive",
            created_at=datetime.now().isoformat(),
            config=config
        )
        
        self.profiles.append(profile)
        self.save_profiles()
        return profile

    def get_profiles(self) -> List[Profile]:
        """Get all profiles"""
        return self.profiles

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a specific profile by ID"""
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        return None

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile"""
        # Stop browser if active
        if self.camoufox_manager.is_session_active(profile_id):
            asyncio.create_task(self.camoufox_manager.close_browser_session(profile_id))
        
        # Remove from profiles list
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        self.save_profiles()
        return True

    def generate_camoufox_config(self, os: str, timezone: str) -> Dict[str, Any]:
        """Generate baseline Camoufox configuration based on OS and timezone."""
        return {
            "os": os,
            "timezone": timezone,
            "locale:language": "en",
            "locale:region": "US",
            "humanize": True,
            "showcursor": True,
            "headless": False,
        }

    async def launch_browser(self, profile_id: str) -> bool:
        """Launch a browser instance for the profile"""
        try:
            profile = self.get_profile(profile_id)
            if not profile:
                return False

            # Ensure we always pass a concrete config to the manager
            config = profile.config or self.generate_camoufox_config(
                profile.os, profile.timezone
            )
            config["showcursor"] = True
            config["headless"] = False
            profile.config = config

            # Use the enhanced Camoufox manager
            success = await self.camoufox_manager.create_browser_session(
                profile_id, config, profile.os
            )
            
            if success:
                # Update profile status
                profile.status = "active"
                self.save_profiles()
                logger.info(f"Browser launched for profile {profile.name} ({profile_id})")
            
            return success

        except Exception as e:
            logger.error(f"Error launching browser for profile {profile_id}: {e}")
            return False

    async def stop_browser(self, profile_id: str) -> bool:
        """Stop a browser instance"""
        try:
            success = await self.camoufox_manager.close_browser_session(profile_id)
            
            if success:
                # Update profile status
                profile = self.get_profile(profile_id)
                if profile:
                    profile.status = "inactive"
                    self.save_profiles()
                logger.info(f"Browser stopped for profile {profile_id}")
            
            return success

        except Exception as e:
            logger.error(f"Error stopping browser for profile {profile_id}: {e}")
            return False

# Initialize profile manager
profile_manager = ProfileManager()

# API Routes
@app.get("/api/profiles", response_model=List[Profile])
async def get_profiles():
    """Get all profiles"""
    return profile_manager.get_profiles()

@app.post("/api/profiles", response_model=Profile)
async def create_profile(profile_data: ProfileCreate):
    """Create a new profile"""
    try:
        profile = profile_manager.create_profile(profile_data)
        return profile
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to create profile")

@app.get("/api/profiles/{profile_id}", response_model=Profile)
async def get_profile(profile_id: str):
    """Get a specific profile"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """Delete a profile"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    success = profile_manager.delete_profile(profile_id)
    if success:
        return {"message": "Profile deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete profile")

@app.post("/api/profiles/{profile_id}/launch")
async def launch_profile(profile_id: str, background_tasks: BackgroundTasks):
    """Launch a browser instance for the profile"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if profile_manager.camoufox_manager.is_session_active(profile_id):
        raise HTTPException(status_code=400, detail="Profile is already active")
    
    # Launch browser in background
    background_tasks.add_task(profile_manager.launch_browser, profile_id)
    
    return {"message": "Browser launch initiated"}

@app.post("/api/profiles/{profile_id}/stop")
async def stop_profile(profile_id: str, background_tasks: BackgroundTasks):
    """Stop a browser instance for the profile"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if not profile_manager.camoufox_manager.is_session_active(profile_id):
        raise HTTPException(status_code=400, detail="Profile is not active")
    
    # Stop browser in background
    background_tasks.add_task(profile_manager.stop_browser, profile_id)
    
    return {"message": "Browser stop initiated"}

@app.get("/api/profiles/{profile_id}/status")
async def get_profile_status(profile_id: str):
    """Get the current status of a profile"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    session_info = profile_manager.camoufox_manager.get_session_info(profile_id)
    
    return {
        "profile_id": profile_id,
        "status": "active" if session_info else "inactive",
        "session_info": session_info
    }

@app.post("/api/profiles/{profile_id}/test")
async def test_profile_browser(profile_id: str):
    """Test if the browser is working by navigating to a URL"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if not profile_manager.camoufox_manager.is_session_active(profile_id):
        raise HTTPException(status_code=400, detail="Profile is not active")
    
    try:
        # Navigate to a test URL
        success = await profile_manager.camoufox_manager.navigate_to_url(profile_id, "https://httpbin.org/user-agent")
        if success:
            return {"message": "Browser test successful - navigated to test URL"}
        else:
            return {"message": "Browser test failed - could not navigate"}
    except Exception as e:
        logger.error(f"Browser test error: {e}")
        raise HTTPException(status_code=500, detail=f"Browser test failed: {str(e)}")

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML file"""
    return FileResponse("../frontend/index.html")

@app.get("/app.js")
async def serve_js():
    """Serve the JavaScript file"""
    return FileResponse("../frontend/app.js")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    active_sessions = profile_manager.camoufox_manager.get_active_sessions()
    return {
        "status": "healthy",
        "active_browsers": len(active_sessions),
        "total_profiles": len(profile_manager.profiles),
        "active_sessions": active_sessions
    }

# Additional API endpoints for enhanced functionality
@app.post("/api/profiles/{profile_id}/navigate")
async def navigate_profile(profile_id: str, url: str):
    """Navigate to a URL in the specified profile's browser"""
    profile = profile_manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if not profile_manager.camoufox_manager.is_session_active(profile_id):
        raise HTTPException(status_code=400, detail="Profile is not active")
    
    success = await profile_manager.camoufox_manager.navigate_to_url(profile_id, url)
    if success:
        return {"message": f"Navigated to {url}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to navigate")

@app.get("/api/sessions")
async def get_active_sessions():
    """Get all active browser sessions"""
    return profile_manager.camoufox_manager.get_active_sessions()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=12000)
