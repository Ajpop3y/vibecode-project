"""
Google Drive Authentication Helper for VibeCode.
Run this script to generate your 'token.json' file.
"""
import os
import sys
import socket
from google_auth_oauthlib.flow import InstalledAppFlow

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SECRETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/secrets"
CREDENTIALS_FILE = os.path.join(SECRETS_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SECRETS_DIR, "token.json")

def find_free_port():
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def authenticate():
    print(f"Checking credentials at: {CREDENTIALS_FILE}")
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: Credentials file not found at {CREDENTIALS_FILE}")
        print("Please verify the file name and location.")
        return

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES)
            
        print("\n--- GOOGLE DRIVE AUTHENTICATION ---")
        print("1. A browser window should open automatically.")
        print("2. Log in with your Google Account.")
        print("3. Allow access to 'See and download all your Google Drive files'.")
        print("4. The browser will redirect to localhost and say 'Authentication successful'.")
        print("----------------------------------\n")
        
        # Try a specific port strategy or dynamic
        # Using port 0 lets the OS pick a free port (avoid conflicts)
        creds = flow.run_local_server(
            port=0, 
            prompt='consent',
            authorization_prompt_message="Waiting for authentication... (Check your browser)",
            success_message="Authentication successful! You can close this window now.",
            open_browser=True
        )
        
        # Save the credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
        print(f"\nSUCCESS! Token saved to: {TOKEN_FILE}")
        print("You can now run VibeCode normally.")
        
    except Exception as e:
        print(f"\n\nERROR during authentication: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure 'credentials.json' is a valid OAuth 2.0 Client ID (Desktop App).")
        print("2. Check if your firewall is blocking Python from opening a port.")
        print("3. Try running this script again.")

if __name__ == "__main__":
    authenticate()
