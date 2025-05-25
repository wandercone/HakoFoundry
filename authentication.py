import logging
from nicegui import ui, app
import os
import secrets
import time
from typing import Dict
from functools import wraps

# Configure logging
logger = logging.getLogger("foundry_logger")

def load_auth_from_env() -> Dict[str, str]:
    """Load authentication credentials from environment variables."""
    auth_users = {}
 
    # Check environment variables first
    admin_user = os.getenv('ADMIN_USERNAME')
    admin_pass = os.getenv('ADMIN_PASSWORD')
    
    if admin_user and admin_pass:
        auth_users[admin_user] = admin_pass
    
    # Multi-user configuration (AUTH_USER_1, AUTH_PASS_1, etc.)
    i = 1
    while True:
        user_var = f'AUTH_USER_{i}'
        pass_var = f'AUTH_PASS_{i}'
        
        username = os.getenv(user_var)
        password = os.getenv(pass_var)
        
        if username and password:
            auth_users[username] = password
            i += 1
        else:
            break
    
    return auth_users

AUTH_USERS = load_auth_from_env()

valid_sessions: Dict[str, Dict] = {}  # session_token -> {username, created_at, last_seen}

def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password against environment variables."""
    if not AUTH_USERS:
        logger.warning("No authentication credentials found in environment variables!")
        return False
        
    return AUTH_USERS.get(username) == password

def get_session_token() -> str:
    """Get session token from browser storage (naturally isolated per browser)."""
    try:
        # app.storage.browser is automatically different for each browser instance
        session_token = app.storage.browser.get('session_token')
        if not session_token:
            # Create new session token for this browser
            session_token = secrets.token_urlsafe(32)
            app.storage.browser['session_token'] = session_token
            logger.info(f"Created new session token for browser: {session_token[:8]}...")
        return session_token
    except Exception as e:
        logger.error(f"Error accessing browser storage: {e}")
        return secrets.token_urlsafe(32)

def is_authenticated() -> bool:
    """Check if current browser session is authenticated."""
    # If no authentication is configured, allow open access
    if not AUTH_USERS:
        logger.debug("No authentication configured - allowing open access")
        return True
    
    try:
        # Get session token from THIS browser's storage
        session_token = get_session_token()
        
        # Check if this session token is valid in our global session store
        if session_token not in valid_sessions:
            logger.debug(f"Valid session not found: {session_token[:8]}...")
            return False
        
        # Update last seen time
        valid_sessions[session_token]['last_seen'] = time.time()
        
        username = valid_sessions[session_token]['username']
        logger.debug(f"Valid session for {username} in: {session_token[:8]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error in authenticating: {e}")
        return False

def authenticate_session(username: str):
    """Mark current browser session as authenticated."""
    try:
        session_token = get_session_token()
        valid_sessions[session_token] = {
            'username': username,
            'created_at': time.time(),
            'last_seen': time.time()
        }
        app.storage.browser['username'] = username
        
        logger.info(f"Authenticated session for {username}: {session_token[:8]}...")
        
    except Exception as e:
        logger.error(f"Error in authenticating session: {e}")

def logout_session():
    """Remove authentication for current browser session."""
    try:
        session_token = get_session_token()
        if session_token in valid_sessions:
            username = valid_sessions[session_token]['username']
            del valid_sessions[session_token]
            logger.info(f"Logged out {username}: {session_token[:8]}...")
        app.storage.browser.clear()
        
    except Exception as e:
        logger.error(f"Error logging out: {e}")

def get_current_user() -> str:
    """Get current authenticated username."""
    # If no authentication configured, return generic user
    if not AUTH_USERS:
        return 'Guest'
    
    try:
        username = app.storage.browser.get('username')
        if username:
            return username
        session_token = get_session_token()
        session_data = valid_sessions.get(session_token, {})
        return session_data.get('username', 'Unknown')
    except:
        return 'Unknown'

def cleanup_expired_sessions(max_age_hours: int = 24):
    """Clean up old sessions."""
    current_time = time.time()
    expired_sessions = []
    
    for token, data in valid_sessions.items():
        age_hours = (current_time - data['last_seen']) / 3600
        if age_hours > max_age_hours:
            expired_sessions.append(token)
    
    for token in expired_sessions:
        username = valid_sessions[token]['username']
        del valid_sessions[token]
        logger.info(f"Cleaned up expired session for {username}: {token[:8]}...")

def create_login_page():
    """Create login page UI."""

    def handle_login():
        username = username_input.value.strip()
        password = password_input.value
        
        logger.info(f"Login attempt: {username}")
        
        if not AUTH_USERS:
            error_label.text = 'Authentication not configured. Check environment variables.'
            error_label.visible = True
            return
        
        if verify_credentials(username, password):
            logger.info(f"Credentials valid for {username}")
            authenticate_session(username)
            
            # Redirect to main page
            ui.timer(0.1, lambda: ui.navigate.to('/overview'), once=True)
        else:
            logger.warning(f"Invalid credentials for {username}")
            error_label.text = 'Invalid credentials'
            error_label.visible = True
            password_input.value = ''
    
    with ui.column().classes('absolute-center'):
        with ui.card().classes('p-8').style('width: 30vw'):
            with ui.row().classes('w-full'):
                with ui.link(target='http://hakoforge.com', new_tab=True).classes('w-full'):
                    ui.image('res/Foundry_Logo.png')
                username_input = ui.input('Username').classes('w-full mb-4')
                password_input = ui.input('Password', password=True).classes('w-full mb-4')
                
                error_label = ui.label('').classes('text-red-500 text-sm mb-4')
                error_label.visible = False
                
                ui.button('Login', on_click=handle_login).classes('w-full border-solid border-2 border-[#ffdd00]').props('flat color="white"')
                password_input.on('keydown.enter', handle_login)
                ui.space().classes('h-6')
            with ui.row().classes('justify-center w-full'):
                with ui.link(target='https://discord.com/invite/3kjpbmckgm'):
                    ui.image('res/Discord_Icon.png').style('width: 50px')
                with ui.link(target='https://www.reddit.com/r/hakoforge/'):
                    ui.image('res/Reddit_Icon.png').style('width: 50px')
                with ui.link(target='https://www.youtube.com/@HakoForge'):
                    ui.image('res/YouTube_Icon.png').style('width: 50px')
                with ui.link(target='https://www.instagram.com/hakoforge'):
                    ui.image('res/Instagram_Icon.png').style('width: 50px')
                with ui.link(target='https://twitter.com/HakoForge'):
                    ui.image('res/X_Icon.png').style('width: 50px')
                with ui.link(target='https://www.tiktok.com/@hakoforge'):
                    ui.image('res/TikTok_Icon.png').style('width: 50px')
                with ui.link(target='https://github.com/hakoforge'):
                    ui.image('res/Git_Icon.png').style('width: 50px')

def require_auth(page_func):
    """Decorator to require authentication for a page."""
    @wraps(page_func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Checking auth for {page_func.__name__}")
        if not is_authenticated():
            logger.debug("Not authenticated, showing login")
            create_login_page()
            return
        logger.debug(f"Authenticated, showing {page_func.__name__}")
        return page_func(*args, **kwargs)
    return wrapper
    
# Periodic cleanup of old sessions
ui.timer(3600, lambda: cleanup_expired_sessions(24), active=True)  # Clean up every hour

# Startup validation
def validate_environment() -> bool:
    """Validate environment configuration on startup."""
    if not AUTH_USERS:
        logger.warning("OPEN ACCESS MODE: No authentication credentials found!")
        logger.warning("The site will be accessible without login.")
        return False  # Return False to indicate no auth configured
    else:
        logger.info(f"AUTHENTICATION ENABLED: {len(AUTH_USERS)} user(s) configured")
        for username in AUTH_USERS.keys():
            logger.info(f"   - {username}")
        logger.info("   Site is protected and requires login.")
        return True  # Return True to indicate auth is configured