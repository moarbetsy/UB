import logging
from dataclasses import asdict
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CamoufoxManager:
    """Enhanced Camoufox browser management with advanced fingerprinting"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_configs: Dict[str, Dict[str, Any]] = {}
        
    async def create_browser_session(self, profile_id: str, config: Dict[str, Any], os_name: str) -> bool:
        """Create a new Camoufox browser session with advanced fingerprinting"""
        try:
            # Import Camoufox modules
            from camoufox import AsyncCamoufox
            from browserforge.fingerprints import FingerprintGenerator
            
            # Generate enhanced fingerprint using BrowserForge
            generator = FingerprintGenerator()
            fingerprint_data = generator.generate()
            fingerprint: Dict[str, Any] = asdict(fingerprint_data)
            
            base_config = config.copy()
            base_config.pop("os", None)
            humanize_option = base_config.pop("humanize", True)
            headless_option = base_config.pop("headless", False)
            # Ensure pointer feedback for interactive sessions
            if not base_config.get("showcursor", True):
                base_config["showcursor"] = True
            os_key = os_name.lower() if os_name else "windows"
            
            browser_manager = AsyncCamoufox(
                config=base_config,
                fingerprint=fingerprint_data,
                os=os_key,
                headless=headless_option,
                humanize=humanize_option,
                i_know_what_im_doing=True,
            )
            browser = await browser_manager.__aenter__()
            
            # Create a new page
            page = await browser.new_page()
            await page.bring_to_front()  # Ensure the new window is focused for user input
            session_config = {
                **base_config,
                "os": os_name,
                "humanize": humanize_option,
                "headless": headless_option,
            }
            
            # Store session information
            self.active_sessions[profile_id] = {
                "browser_manager": browser_manager,
                "browser": browser,
                "page": page,
                "config": session_config,
                "created_at": datetime.now().isoformat(),
                "fingerprint": fingerprint
            }
            
            self.session_configs[profile_id] = session_config
            
            logger.info(f"Browser session created for profile {profile_id}")
            return True
            
        except ImportError as e:
            logger.error(f"Camoufox or BrowserForge not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error creating browser session for profile {profile_id}: {e}")
            return False
    
    async def close_browser_session(self, profile_id: str) -> bool:
        """Close a browser session"""
        try:
            if profile_id not in self.active_sessions:
                return False
                
            session = self.active_sessions[profile_id]
            browser_manager = session["browser_manager"]
            
            # Close the browser
            await browser_manager.__aexit__(None, None, None)
            
            # Remove from active sessions
            del self.active_sessions[profile_id]
            if profile_id in self.session_configs:
                del self.session_configs[profile_id]
            
            logger.info(f"Browser session closed for profile {profile_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing browser session for profile {profile_id}: {e}")
            return False
    
    def get_session_info(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get information about an active session"""
        if profile_id not in self.active_sessions:
            return None
            
        session = self.active_sessions[profile_id]
        return {
            "profile_id": profile_id,
            "created_at": session["created_at"],
            "uptime": (datetime.now() - datetime.fromisoformat(session["created_at"])).total_seconds(),
            "fingerprint_summary": self._get_fingerprint_summary(session["fingerprint"]),
            "config_summary": self._get_config_summary(session["config"])
        }
    
    def is_session_active(self, profile_id: str) -> bool:
        """Check if a session is active"""
        return profile_id in self.active_sessions
    
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active sessions"""
        sessions: Dict[str, Dict[str, Any]] = {}
        for profile_id in self.active_sessions:
            session_info = self.get_session_info(profile_id)
            if session_info is not None:
                sessions[profile_id] = session_info
        return sessions
    
    async def navigate_to_url(self, profile_id: str, url: str) -> bool:
        """Navigate to a URL in the specified profile's browser"""
        try:
            if profile_id not in self.active_sessions:
                return False
                
            session = self.active_sessions[profile_id]
            page = session["page"]
            
            await page.goto(url)
            logger.info(f"Navigated to {url} in profile {profile_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to {url} in profile {profile_id}: {e}")
            return False
    
    def _get_geolocation_from_timezone(self, timezone: str) -> Dict[str, float]:
        """Get approximate geolocation based on timezone"""
        # Simplified mapping of timezones to approximate coordinates
        timezone_coords = {
            "GMT-12:00": {"latitude": -14.2710, "longitude": -170.1322},  # Baker Island
            "GMT-11:00": {"latitude": 21.3099, "longitude": -157.8581},   # Hawaii
            "GMT-10:00": {"latitude": 61.2181, "longitude": -149.9003},   # Alaska
            "GMT-09:00": {"latitude": 37.7749, "longitude": -122.4194},   # San Francisco
            "GMT-08:00": {"latitude": 34.0522, "longitude": -118.2437},   # Los Angeles
            "GMT-07:00": {"latitude": 39.7392, "longitude": -104.9903},   # Denver
            "GMT-06:00": {"latitude": 29.7604, "longitude": -95.3698},    # Houston
            "GMT-05:00": {"latitude": 40.7128, "longitude": -74.0060},    # New York
            "GMT-04:00": {"latitude": 25.7617, "longitude": -80.1918},    # Miami
            "GMT-03:00": {"latitude": -23.5505, "longitude": -46.6333},   # São Paulo
            "GMT-02:00": {"latitude": -22.9068, "longitude": -43.1729},   # Rio de Janeiro
            "GMT-01:00": {"latitude": 32.6612, "longitude": -16.9244},    # Madeira
            "GMT+00:00": {"latitude": 51.5074, "longitude": -0.1278},     # London
            "GMT+01:00": {"latitude": 52.5200, "longitude": 13.4050},     # Berlin
            "GMT+02:00": {"latitude": 59.3293, "longitude": 18.0686},     # Stockholm
            "GMT+03:00": {"latitude": 55.7558, "longitude": 37.6176},     # Moscow
            "GMT+04:00": {"latitude": 25.2048, "longitude": 55.2708},     # Dubai
            "GMT+05:00": {"latitude": 28.6139, "longitude": 77.2090},     # Delhi
            "GMT+06:00": {"latitude": 23.8103, "longitude": 90.4125},     # Dhaka
            "GMT+07:00": {"latitude": 13.7563, "longitude": 100.5018},    # Bangkok
            "GMT+08:00": {"latitude": 39.9042, "longitude": 116.4074},    # Beijing
            "GMT+09:00": {"latitude": 35.6762, "longitude": 139.6503},    # Tokyo
            "GMT+10:00": {"latitude": -33.8688, "longitude": 151.2093},   # Sydney
            "GMT+11:00": {"latitude": -37.8136, "longitude": 144.9631},   # Melbourne
            "GMT+12:00": {"latitude": -36.8485, "longitude": 174.7633},   # Auckland
        }
        
        return timezone_coords.get(timezone, {"latitude": 51.5074, "longitude": -0.1278})
    
    def _get_fingerprint_summary(self, fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of the fingerprint for display"""
        summary = {}
        
        if "navigator" in fingerprint:
            nav = fingerprint["navigator"]
            summary["user_agent"] = nav.get("userAgent", "Unknown")
            summary["platform"] = nav.get("platform", "Unknown")
            summary["language"] = nav.get("language", "Unknown")
        
        if "screen" in fingerprint:
            screen = fingerprint["screen"]
            summary["screen_resolution"] = f"{screen.get('width', 0)}x{screen.get('height', 0)}"
        
        return summary
    
    def _get_config_summary(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of the configuration for display"""
        return {
            "timezone": config.get("timezone", "Unknown"),
            "humanize": config.get("humanize", False),
            "addons_count": len(config.get("addons", [])),
            "fonts_count": len(config.get("fonts", []))
        }
