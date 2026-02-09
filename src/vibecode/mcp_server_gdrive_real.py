"""
Real Google Drive MCP Server for VibeCode.
Connects to actual Google Drive API using OAuth 2.0.
"""
import os.path
import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("google_drive_real")

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SECRETS_DIR = os.path.dirname(os.path.abspath(__file__)) + "/secrets"
CREDENTIALS_FILE = os.path.join(SECRETS_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SECRETS_DIR, "token.json")

def get_service():
    """Authenticate and return the Drive API service."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Credentials file not found at {CREDENTIALS_FILE}")
                
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

@mcp.tool()
def gdrive_list(limit: int = 10, folder_id: str = None) -> str:
    """
    List files in Google Drive.
    
    Args:
        limit: Max number of files to return (default 10)
        folder_id: Optional folder ID to list contents of
        
    Returns:
        JSON string of file list
    """
    try:
        service = get_service()
        
        query = "trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
            
        results = service.files().list(
            pageSize=limit,
            q=query,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime)"
        ).execute()
        
        items = results.get('files', [])
        if not items:
            return "No files found."
            
        return str(items)
        
    except HttpError as error:
        return f"An error occurred: {error}"
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def gdrive_search(query: str, limit: int = 10) -> str:
    """
    Search for files in Google Drive by name or content.
    
    Args:
        query: Search term
        limit: Max results
        
    Returns:
        JSON string of matching files
    """
    try:
        service = get_service()
        
        # Search in name or content
        q = f"name contains '{query}' and trashed = false"
        
        results = service.files().list(
            pageSize=limit,
            q=q,
            fields="files(id, name, mimeType, webViewLink)"
        ).execute()
        
        items = results.get('files', [])
        if not items:
            return f"No files found matching '{query}'"
            
        return str(items)
        
    except HttpError as error:
        return f"An error occurred: {error}"
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def gdrive_read(file_id: str) -> str:
    """
    Read the content of a Google Drive file.
    Auto-exports Google Docs to plain text.
    
    Args:
        file_id: ID of the file to read
        
    Returns:
        Content of the file
    """
    try:
        service = get_service()
        
        # Get metadata to check mimeType
        file_meta = service.files().get(fileId=file_id).execute()
        mime_type = file_meta.get('mimeType')
        name = file_meta.get('name')
        
        content = ""
        
        # Handle Google Docs
        if mime_type == 'application/vnd.google-apps.document':
            content = service.files().export_media(
                fileId=file_id,
                mimeType='text/plain'
            ).execute().decode('utf-8')
            
        # Handle Google Sheets (export to CSV-like format)
        elif mime_type == 'application/vnd.google-apps.spreadsheet':
             content = service.files().export_media(
                fileId=file_id,
                mimeType='text/csv'
            ).execute().decode('utf-8')
            
        # Handle binary/text files
        else:
            content = service.files().get_media(fileId=file_id).execute().decode('utf-8')
            
        return f"--- FILE: {name} ({file_id}) ---\n\n{content}"
        
    except HttpError as error:
        return f"An error occurred: {error}"
    except Exception as e:
        return f"Error reading file: {e}"

if __name__ == "__main__":
    # Force authentication on startup
    print("Initializing Google Drive Auth...")
    get_service()
    mcp.run()
