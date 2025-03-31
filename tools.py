import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pathlib import Path
import json

from models import Email, EmailSummary, CalendarEvent
from config import settings

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=settings.LOG_FILE
)
logger = logging.getLogger(__name__)

class GmailTools:
    """Tools for interacting with Gmail API."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send'
    ]
    
    def __init__(self, credentials: Credentials):
        """Initialize Gmail tools."""
        self.service = build('gmail', 'v1', credentials=credentials)
        logger.info("Successfully initialized Gmail service")
    
    def get_all_emails(self, max_results: int = 10, unread_only: bool = False) -> List[Email]:
        """Get emails from Gmail based on filters."""
        try:
            query = 'is:unread' if unread_only else ''
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id']
                ).execute()
                
                headers = msg['payload']['headers']
                subject = next(h['value'] for h in headers if h['name'] == 'Subject')
                sender = next(h['value'] for h in headers if h['name'] == 'From')
                recipient = next(h['value'] for h in headers if h['name'] == 'To')
                
                # Get email content
                if 'parts' in msg['payload']:
                    content = msg['payload']['parts'][0]['body']['data']
                else:
                    content = msg['payload']['body']['data']
                
                emails.append(Email(
                    id=message['id'],
                    subject=subject,
                    sender=sender,
                    recipient=recipient,
                    content=content,
                    timestamp=datetime.fromtimestamp(int(msg['internalDate'])/1000),
                    is_read='UNREAD' in msg['labelIds']
                ))
            
            return emails
        except Exception as e:
            logger.error(f"Error getting emails: {str(e)}")
            raise
    
    def create_email(self, to: str, subject: str, content: str) -> bool:
        """Create and send an email."""
        try:
            message = {
                'raw': self._create_message(to, subject, content)
            }
            
            self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Email sent successfully to {to}")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def get_email(self, email_id: str) -> Optional[Email]:
        """Get a specific email by ID."""
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=email_id
            ).execute()
            
            headers = msg['payload']['headers']
            subject = next(h['value'] for h in headers if h['name'] == 'Subject')
            sender = next(h['value'] for h in headers if h['name'] == 'From')
            recipient = next(h['value'] for h in headers if h['name'] == 'To')
            
            if 'parts' in msg['payload']:
                content = msg['payload']['parts'][0]['body']['data']
            else:
                content = msg['payload']['body']['data']
            
            return Email(
                id=email_id,
                subject=subject,
                sender=sender,
                recipient=recipient,
                content=content,
                timestamp=datetime.fromtimestamp(int(msg['internalDate'])/1000),
                is_read='UNREAD' not in msg['labelIds']
            )
        except Exception as e:
            logger.error(f"Error getting email {email_id}: {str(e)}")
            return None
    
    def _create_message(self, to: str, subject: str, content: str) -> str:
        """Create a message in base64url format."""
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(content)
        message['to'] = to
        message['subject'] = subject
        
        return base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

class CalendarTools:
    """Tools for interacting with Google Calendar API."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    def __init__(self, credentials: Credentials):
        """Initialize calendar tools with credentials."""
        self.credentials = credentials
        self.service = build('calendar', 'v3', credentials=credentials)
    
    def list_events(self, start_date: Optional[str] = None, end_date: Optional[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """List calendar events."""
        try:
            # Convert dates to RFC 3339 format if provided
            if start_date:
                # If only date is provided, set time to start of day
                if 'T' not in start_date:
                    start_date = f"{start_date}T00:00:00Z"
            if end_date:
                # If only date is provided, set time to end of day
                if 'T' not in end_date:
                    end_date = f"{end_date}T23:59:59Z"
            
            logger.info(f"Listing calendar events from {start_date} to {end_date}")
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_date,
                timeMax=end_date,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} events")
            return events
            
        except Exception as e:
            logger.error(f"Error listing calendar events: {str(e)}", exc_info=True)
            raise
    
    def create_event(self, summary: str, description: str, start_date: str, duration_minutes: int = 60, attendees: List[str] = None, location: str = None) -> Optional[Dict]:
        """Create a new calendar event."""
        try:
            logger.info(f"Creating calendar event: {summary}")
            logger.info(f"Start date: {start_date}")
            logger.info(f"Duration: {duration_minutes} minutes")
            logger.info(f"Attendees: {attendees}")
            logger.info(f"Location: {location}")
            
            # Parse the start date
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                
                # Format dates in RFC 3339 format with timezone
                event = {
                    'summary': summary,
                    'description': description,
                    'start': {
                        'dateTime': start_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'timeZone': 'UTC'
                    },
                    'end': {
                        'dateTime': end_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'timeZone': 'UTC'
                    }
                }
                
                # Add optional fields
                if attendees:
                    event['attendees'] = [{'email': email} for email in attendees]
                if location:
                    event['location'] = location
                
                logger.info(f"Formatted event data: {event}")
                
                # Create the event
                event = self.service.events().insert(
                    calendarId='primary',
                    body=event,
                    sendUpdates='all'
                ).execute()
                
                logger.info(f"Successfully created event: {event['id']}")
                return event
                
            except ValueError as e:
                logger.error(f"Error parsing date: {str(e)}")
                raise ValueError(f"Invalid date format: {start_date}. Please use ISO format (YYYY-MM-DDTHH:MM:SSZ)")
                
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}", exc_info=True)
            raise
    
    def check_availability(self, start_date: str, end_date: str, duration_minutes: int = 60) -> List[Dict[str, str]]:
        """Check for available time slots between start and end dates."""
        try:
            logger.info(f"Checking availability from {start_date} to {end_date}")
            
            # Convert dates to RFC 3339 format if needed
            if 'T' not in start_date:
                start_date = f"{start_date}T00:00:00Z"
            if 'T' not in end_date:
                end_date = f"{end_date}T23:59:59Z"
            
            # Get all events in the time range
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_date,
                timeMax=end_date,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Found {len(events)} existing events")
            
            # Sort events by start time
            events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
            
            # Find available slots
            available_slots = []
            current_time = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            for event in events:
                event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')).replace('Z', '+00:00'))
                
                # Check if there's enough time before this event
                if (event_start - current_time).total_seconds() >= duration_minutes * 60:
                    slot_end = current_time + timedelta(minutes=duration_minutes)
                    if slot_end <= event_start:
                        available_slots.append({
                            'start': current_time.strftime("%Y-%m-%d %I:%M %p"),
                            'end': slot_end.strftime("%Y-%m-%d %I:%M %p")
                        })
                
                # Update current time to after this event
                event_end = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')).replace('Z', '+00:00'))
                current_time = event_end
            
            # Check if there's time after the last event
            if (end_time - current_time).total_seconds() >= duration_minutes * 60:
                slot_end = current_time + timedelta(minutes=duration_minutes)
                if slot_end <= end_time:
                    available_slots.append({
                        'start': current_time.strftime("%Y-%m-%d %I:%M %p"),
                        'end': slot_end.strftime("%Y-%m-%d %I:%M %p")
                    })
            
            logger.info(f"Found {len(available_slots)} available slots")
            return available_slots
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}", exc_info=True)
            raise

class GoogleAPITools:
    """Main class for managing Google API authentication and tools."""
    
    def __init__(self):
        """Initialize Google API tools."""
        self.creds = None
        self.gmail = None
        self.calendar = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Google APIs."""
        try:
            if Path(settings.GOOGLE_API_CREDENTIALS).exists():
                # Combine scopes from both tools
                scopes = GmailTools.SCOPES + CalendarTools.SCOPES
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(settings.GOOGLE_API_CREDENTIALS),
                    scopes,
                    redirect_uri='http://localhost:8080/'
                )
                self.creds = flow.run_local_server(
                    port=8080,
                    success_message='The authentication flow has completed. You may close this window.',
                    open_browser=True
                )
                
                # Initialize both tools with the credentials
                self.gmail = GmailTools(self.creds)
                self.calendar = CalendarTools(self.creds)
                logger.info("Successfully authenticated with Google APIs")
            else:
                raise FileNotFoundError("Google Calendar credentials file not found")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise 