import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import openai
import json
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from config import settings
from models import Email, EmailSummary, ConversationHistory, Message
from tools import GoogleAPITools

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=settings.LOG_FILE
)
logger = logging.getLogger(__name__)

# Initialize OpenAI
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

class CalendarAgent:
    """Main agent class for handling calendar and email operations."""
    
    def __init__(self):
        """Initialize the calendar agent."""
        self.console = Console()
        self.tools = GoogleAPITools()
        self.conversation = ConversationHistory()
        self._setup_system_prompt()
    
    def _setup_system_prompt(self) -> None:
        """Set up the system prompt for the AI model."""
        current_date = datetime.now().strftime("%B %d, %Y")
        self.system_prompt = f"""You are a helpful calendar and email assistant that can understand natural language requests and map them to specific actions.
Current date: {current_date}

Your capabilities include:
1. Email Management:
   - Reading and summarizing emails
   - Creating and sending emails
   - Retrieving specific emails
2. Calendar Management:
   - Managing calendar events
   - Scheduling meetings
   - Checking availability

When processing requests, follow these steps:
1. Identify the user's intent and required actions
2. Extract relevant parameters (e.g., number of emails, time period)
3. Map the request to available tools and actions
4. Execute the actions in the correct sequence
5. Format the response appropriately

Example request: "Can you summarize my last 3 unread emails?"
Inferred actions:
1. Fetch last 3 unread emails
2. Read content of each email
3. Generate a concise summary (< 500 words)

Available tools:
- Email summarization: summarize_emails(count, unread_only=True)
- Email retrieval: get_email(email_id)
- Email sending: send_email(to, subject, content)

IMPORTANT:
- Do not hallucinate. If you don't know the answer, say so and suggest alternative actions.
- When processing dates, consider the current date ({current_date}) as reference.
- For relative dates (e.g., "next week", "tomorrow"), calculate based on the current date.
Please format your responses in markdown and be concise but informative.
If you're unsure about any action, ask for clarification.
"""
    
    def _get_ai_response(self, user_input: str) -> str:
        """Get a response from the AI model."""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                *[{"role": msg.role, "content": msg.content} for msg in self.conversation.messages],
                {"role": "user", "content": user_input}
            ]
            
            try:
                response = client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=messages,
                    max_tokens=settings.MAX_TOKENS
                )
                return response.choices[0].message.content
            except openai.BadRequestError as e:
                if "context_length_exceeded" in str(e):
                    logger.error(f"Token limit exceeded: {str(e)}")
                    raise ValueError("The content is too long for the AI model to process. Please try with fewer emails or shorter content.")
                raise
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            raise
    
    def _truncate_email_content(self, content: str, max_length: int = 1000) -> str:
        """Truncate email content to a maximum length."""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    def _detect_gmail_intent(self, intent: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Detect Gmail intent and extract relevant entities."""
        try:
            # Define intent categories with their key indicators
            intent_categories = {
                'summarize': {
                    'indicators': [
                        "summarize", "summarise", "summary", "summaries", "summarization",
                        "summarisation", "overview", "review", "recap", "recapitulate",
                        "what's in", "what is in", "whats in", "what are my", "what are the",
                        "unread", "inbox", "emails", "messages"
                    ],
                    'entities': ['count', 'unread_only', 'time_period'],
                    'required': []
                },
                'send': {
                    'indicators': [
                        "send", "write", "compose", "draft", "create", "new email",
                        "new message", "write to", "email to", "mail to", "message to",
                        "forward", "reply", "respond", "response"
                    ],
                    'entities': ['to', 'subject', 'content', 'cc', 'bcc'],
                    'required': ['to', 'subject', 'content']
                },
                'retrieve': {
                    'indicators': [
                        "get", "retrieve", "fetch", "find", "search", "look up",
                        "show me", "display", "view", "read", "open", "access",
                        "specific", "particular", "certain", "this email"
                    ],
                    'entities': ['email_id', 'search_query', 'time_period'],
                    'required': ['email_id']
                }
            }
            
            # Extract entities from the intent string
            entities = {}
            for category, info in intent_categories.items():
                if any(indicator in intent.lower() for indicator in info['indicators']):
                    # Extract required entities
                    for entity in info['entities']:
                        if entity in params:
                            entities[entity] = params[entity]
                    
                    # Validate required entities
                    missing_entities = [req for req in info['required'] if req not in entities]
                    if missing_entities:
                        logger.warning(f"Missing required entities for {category} intent: {missing_entities}")
                        return None, None
                    
                    logger.info(f"Detected {category} intent with entities: {entities}")
                    return category, entities
            
            logger.warning(f"No matching intent category found for: {intent}")
            return None, None
            
        except Exception as e:
            logger.error(f"Error in Gmail intent detection: {str(e)}", exc_info=True)
            return None, None

    def _handle_gmail_action(self, analysis_data: Dict[str, Any]) -> str:
        """Handle Gmail-related actions."""
        try:
            logger.info("Processing Gmail request")
            params = analysis_data["parameters"]
            intent = analysis_data["intent"].lower()
            
            # Detect intent and extract entities
            intent_category, entities = self._detect_gmail_intent(intent, params)
            if not intent_category:
                return "## ❌ Unclear Intent\nI couldn't determine what email action you want to perform. Please try again with more specific details."
            
            # Handle different intent categories
            if intent_category == 'summarize':
                try:
                    logger.info("Processing email summarization request")
                    count = entities.get('count', 5)
                    logger.info(f"Requested email count: {count}")
                    
                    logger.info("Calling summarize_emails method")
                    summary = self.summarize_emails(count)
                    logger.info(f"Received summary with {summary.total_emails} emails")
                    
                    # Create the email list separately
                    email_list = []
                    for email in summary.recent_emails:
                        email_list.append(f"• **{email.subject}**\n  From: {email.sender}\n  Date: {email.timestamp.strftime('%Y-%m-%d %H:%M')}")
                    
                    return f"""## 📧 Email Summary

### 📊 Overview
- **Total Emails:** {summary.total_emails}
- **Unread Count:** {summary.unread_count}

### 📝 AI-Generated Summary
{summary.summary}

### 📋 Recent Emails
{chr(10).join(email_list)}"""
                except ValueError as e:
                    return f"I encountered an error while summarizing emails: {str(e)}"
                except Exception as e:
                    logger.error(f"Error in summarize_emails: {str(e)}", exc_info=True)
                    return f"I encountered an unexpected error while summarizing emails: {str(e)}"
            
            elif intent_category == 'send':
                try:
                    logger.info("Processing email send request")
                    logger.info(f"Email details: to={entities.get('to')}, subject={entities.get('subject')}")
                    
                    if self.send_email(
                        entities.get("to"),
                        entities.get("subject"),
                        entities.get("content")
                    ):
                        return "## ✅ Email Sent Successfully"
                    else:
                        return "## ❌ Failed to Send Email"
                except Exception as e:
                    logger.error(f"Error in send_email: {str(e)}", exc_info=True)
                    return f"I encountered an error while sending the email: {str(e)}"
            
            elif intent_category == 'retrieve':
                try:
                    logger.info("Processing email retrieval request")
                    email_id = entities.get("email_id")
                    if not email_id:
                        return "Please provide an email ID to retrieve."
                    
                    logger.info(f"Retrieving email with ID: {email_id}")
                    email = self.get_specific_email(email_id)
                    
                    if email:
                        return f"""## 📧 Email Details

### Message Information
- **Subject:** {email.subject}
- **From:** {email.sender}
- **To:** {email.recipient}
- **Date:** {email.timestamp.strftime('%Y-%m-%d %H:%M')}
- **Status:** {'📖 Read' if email.is_read else '📨 Unread'}

### Content
{email.content}"""
                    else:
                        return "## ❌ Email Not Found"
                except Exception as e:
                    logger.error(f"Error in get_specific_email: {str(e)}", exc_info=True)
                    return f"I encountered an error while retrieving the email: {str(e)}"
            
            return "## ❌ Unsupported Intent\nI couldn't process this email action. Please try again with a different request."
            
        except Exception as e:
            logger.error(f"Error in Gmail action handler: {str(e)}", exc_info=True)
            return f"I encountered an error while processing your email request: {str(e)}"

    def _detect_calendar_intent(self, intent: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Detect calendar intent and extract relevant entities."""
        try:
            # Define intent categories with their key indicators
            intent_categories = {
                'create': {
                    'indicators': ['create', 'schedule', 'add', 'book', 'set up', 'setup', 'arrange', 'plan'],
                    'entities': ['event_title', 'start_date', 'duration', 'attendees', 'location'],
                    'required': ['event_title', 'start_date']
                },
                'list': {
                    'indicators': ['list', 'show', 'display', 'view', 'check', 'retrieve', 'get', 'fetch'],
                    'entities': ['start_date', 'end_date', 'count'],
                    'required': []
                },
                'availability': {
                    'indicators': ['available', 'availability', 'free', 'open', 'when am i free'],
                    'entities': ['start_date', 'end_date', 'duration'],
                    'required': ['start_date', 'end_date', 'duration']
                }
            }
            
            # Extract entities from the intent string
            entities = {}
            for category, info in intent_categories.items():
                if any(indicator in intent.lower() for indicator in info['indicators']):
                    # Extract required entities
                    for entity in info['entities']:
                        if entity in params:
                            entities[entity] = params[entity]
                    
                    # Validate required entities
                    missing_entities = [req for req in info['required'] if req not in entities]
                    if missing_entities:
                        logger.warning(f"Missing required entities for {category} intent: {missing_entities}")
                        return None, None
                    
                    logger.info(f"Detected {category} intent with entities: {entities}")
                    return category, entities
            
            logger.warning(f"No matching intent category found for: {intent}")
            return None, None
            
        except Exception as e:
            logger.error(f"Error in intent detection: {str(e)}", exc_info=True)
            return None, None

    def _handle_calendar_action(self, analysis_data: Dict[str, Any]) -> str:
        """Handle calendar-related actions."""
        try:
            logger.info("Processing calendar request")
            params = analysis_data["parameters"]
            intent = analysis_data["intent"].lower()
            
            # Detect intent and extract entities
            intent_category, entities = self._detect_calendar_intent(intent, params)
            if not intent_category:
                return "## ❌ Unclear Intent\nI couldn't determine what calendar action you want to perform. Please try again with more specific details."
            
            # Handle different intent categories
            if intent_category == 'create':
                try:
                    logger.info("Processing calendar event creation request")
                    event = self.tools.calendar.create_event(
                        summary=entities['event_title'],
                        description=params.get('event_description', ''),
                        start_date=entities['start_date'],
                        duration_minutes=entities.get('duration', 60),
                        attendees=entities.get('attendees', []),
                        location=entities.get('location')
                    )
                    
                    if event:
                        # Format event details for display
                        event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                        event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                        
                        attendee_list = [a.get('email') for a in event.get('attendees', [])]
                        attendee_str = ", ".join(attendee_list) if attendee_list else "No attendees"
                        
                        return f"""## ✅ Event Created Successfully

### Event Details
- **Title:** {event['summary']}
- **Start:** {event_start.strftime("%B %d, %Y at %I:%M %p")}
- **End:** {event_end.strftime("%B %d, %Y at %I:%M %p")}
- **Location:** {event.get('location', 'No location')}
- **Attendees:** {attendee_str}
- **Description:** {event.get('description', 'No description')}"""
                    else:
                        return "## ❌ Failed to Create Event"
                        
                except Exception as e:
                    logger.error(f"Error creating calendar event: {str(e)}", exc_info=True)
                    return f"I encountered an error while creating the calendar event: {str(e)}"
            
            elif intent_category == 'list':
                try:
                    logger.info("Processing calendar listing request")
                    # Get current date as default
                    current_date = datetime.now()
                    
                    # Handle start date
                    start_date = entities.get('start_date')
                    if not start_date:
                        start_date = current_date.strftime("%Y-%m-%d")
                    logger.info(f"Start date: {start_date}")
                    
                    # Handle end date
                    end_date = entities.get('end_date')
                    if not end_date:
                        # Default to 7 days from start date
                        end_date = (current_date + timedelta(days=7)).strftime("%Y-%m-%d")
                    logger.info(f"End date: {end_date}")
                    
                    # Get count parameter
                    count = entities.get('count', 5)
                    logger.info(f"Requested event count: {count}")
                    
                    # List events
                    events = self.tools.calendar.list_events(
                        start_date=start_date,
                        end_date=end_date,
                        max_results=count
                    )
                    
                    if not events:
                        return f"""## 📅 No Events Found

No events found between {start_date} and {end_date}."""
                    
                    # Format dates for display
                    try:
                        display_start = datetime.fromisoformat(start_date.replace('Z', '+00:00')).strftime("%B %d, %Y")
                        display_end = datetime.fromisoformat(end_date.replace('Z', '+00:00')).strftime("%B %d, %Y")
                    except ValueError:
                        # Fallback to raw dates if parsing fails
                        display_start = start_date
                        display_end = end_date
                    
                    # Create event list
                    event_list = []
                    for event in events:
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        end = event['end'].get('dateTime', event['end'].get('date'))
                        
                        # Format event time
                        try:
                            start_time = datetime.fromisoformat(start.replace('Z', '+00:00')).strftime("%I:%M %p")
                            end_time = datetime.fromisoformat(end.replace('Z', '+00:00')).strftime("%I:%M %p")
                            time_str = f"{start_time} - {end_time}"
                        except ValueError:
                            time_str = "All day"
                        
                        # Get attendees
                        attendees = event.get('attendees', [])
                        attendee_list = [f"{a.get('displayName', a.get('email'))}" for a in attendees]
                        attendee_str = ", ".join(attendee_list) if attendee_list else "No attendees"
                        
                        event_list.append(
                            f"• **{event['summary']}**\n"
                            f"  📅 {time_str}\n"
                            f"  📍 {event.get('location', 'No location')}\n"
                            f"  👥 {attendee_str}"
                        )
                    
                    return f"""## 📅 Calendar Events ({display_start} to {display_end})

{chr(10).join(event_list)}"""
                    
                except Exception as e:
                    logger.error(f"Error listing calendar events: {str(e)}", exc_info=True)
                    return f"I encountered an error while listing calendar events: {str(e)}"
            
            elif intent_category == 'availability':
                try:
                    logger.info("Processing availability check request")
                    available_slots = self.tools.calendar.check_availability(
                        start_date=entities['start_date'],
                        end_date=entities['end_date'],
                        duration_minutes=entities['duration']
                    )
                    
                    if not available_slots:
                        return f"""## ⏰ No Available Slots Found

No {entities['duration']}-minute slots available between {entities['start_date']} and {entities['end_date']}."""
                    
                    slots_list = []
                    for slot in available_slots:
                        slots_list.append(f"• {slot['start']} - {slot['end']}")
                    
                    return f"""## ⏰ Available Time Slots

Found {len(available_slots)} available {entities['duration']}-minute slots:

{chr(10).join(slots_list)}"""
                    
                except Exception as e:
                    logger.error(f"Error checking availability: {str(e)}", exc_info=True)
                    return f"I encountered an error while checking availability: {str(e)}"
            
            return "## ❌ Unsupported Intent\nI couldn't process this calendar action. Please try again with a different request."
            
        except Exception as e:
            logger.error(f"Error in calendar action handler: {str(e)}", exc_info=True)
            return f"I encountered an error while processing your calendar request: {str(e)}"

    def _process_command(self, user_input: str) -> str:
        """Process user commands and execute appropriate actions."""
        try:
            logger.info(f"Processing command: {user_input}")
            
            # First, let the AI analyze the request and determine the action
            current_date = datetime.now().strftime("%Y-%m-%d")
            analysis_prompt = f"""Current date: {current_date}

Analyze this request: "{user_input}"
Determine:
1. The user's intent
2. Required actions
3. Parameters needed (including dates, considering current date: {current_date})
4. Available tools to use

Return ONLY a JSON object in this exact format:
{{
    "intent": "string",
    "actions": ["action1", "action2"],
    "parameters": {{
        "start_date": "YYYY-MM-DD",  # Optional, use current date ({current_date}) as reference
        "end_date": "YYYY-MM-DD",    # Optional
        "event_title": "string",     # Optional
        "event_description": "string", # Optional
        "attendees": ["email1", "email2"], # Optional
        "duration_minutes": 60,      # Optional
        "count": 5                   # Optional, for listing events
    }},
    "tools": ["tool1", "tool2"]
}}

For relative dates:
- "today" should be {current_date}
- "tomorrow" should be the next day
- "next week" should be 7 days from {current_date}
- "next month" should be the first day of the next month
- "this week" should be from {current_date} to 6 days later
- "this month" should be from {current_date} to the last day of the current month

Do not include any other text or explanation."""
            
            logger.info("Getting AI analysis of request")
            try:
                analysis = self._get_ai_response(analysis_prompt)
                logger.info(f"Raw AI analysis response: {analysis}")
            except ValueError as e:
                return f"I encountered an error analyzing your request: {str(e)}"
            
            try:
                # Clean the response to ensure it's valid JSON
                analysis = analysis.strip()
                if analysis.startswith('```json'):
                    analysis = analysis[7:]
                if analysis.endswith('```'):
                    analysis = analysis[:-3]
                analysis = analysis.strip()
                logger.info(f"Cleaned analysis response: {analysis}")
                
                # Parse the analysis response using json.loads
                analysis_data = json.loads(analysis)
                logger.info(f"Parsed analysis data: {analysis_data}")
                
                # Define comprehensive intent patterns
                email_intent_patterns = [
                    "email", "mail", "inbox", "message", "correspondence",
                    "send", "write", "compose", "draft", "forward", "reply",
                    "incoming", "outgoing", "unread", "read", "inbox",
                    "mailbox", "correspondence", "communication", "notify",
                    "notification", "alert", "reminder", "announcement"
                ]
                
                calendar_intent_patterns = [
                    "calendar", "schedule", "event", "meeting", "appointment",
                    "booking", "reservation", "plan", "arrange", "organize",
                    "time", "slot", "availability", "free", "busy", "occupied",
                    "upcoming", "future", "date", "day", "week", "month",
                    "agenda", "diary", "timetable", "program", "session",
                    "conference", "call", "interview", "presentation"
                ]
                
                # Get the intent and convert to lowercase for matching
                intent = analysis_data["intent"].lower()
                logger.info(f"Processing intent: {intent}")
                
                # Check for email intent with pattern matching
                email_match = any(pattern in intent for pattern in email_intent_patterns)
                if email_match:
                    logger.info("Detected email intent")
                    return self._handle_gmail_action(analysis_data)
                
                # Check for calendar intent with pattern matching
                calendar_match = any(pattern in intent for pattern in calendar_intent_patterns)
                if calendar_match:
                    logger.info("Detected calendar intent")
                    return self._handle_calendar_action(analysis_data)
                
                # If no specific action is matched, get AI response
                logger.info("No specific intent detected, getting general AI response")
                return self._get_ai_response(user_input)
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing AI analysis as JSON: {str(e)}")
                logger.error(f"Raw AI response: {analysis}")
                return "I encountered an error analyzing your request. Please try rephrasing it."
            except Exception as e:
                logger.error(f"Error parsing AI analysis: {str(e)}")
                logger.error(f"Raw AI response: {analysis}")
                return "I encountered an error analyzing your request. Please try rephrasing it."
            
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            return "I encountered an error processing your command."
    
    def summarize_emails(self, count: int = 5) -> EmailSummary:
        """Summarize recent emails."""
        try:
            logger.info(f"Starting email summarization for {count} emails")
            logger.info("Calling Gmail API to get emails")
            emails = self.tools.gmail.get_all_emails(max_results=count, unread_only=True)
            logger.info(f"Retrieved {len(emails)} emails from Gmail API")
            
            if not emails:
                logger.warning("No emails retrieved from Gmail API")
                raise ValueError("No emails were retrieved. Please check your Gmail API access.")
            
            # Truncate email contents to avoid token limit issues
            truncated_emails = []
            for email in emails:
                truncated_content = self._truncate_email_content(email.content)
                truncated_emails.append(Email(
                    id=email.id,
                    subject=email.subject,
                    sender=email.sender,
                    recipient=email.recipient,
                    content=truncated_content,
                    timestamp=email.timestamp,
                    is_read=email.is_read
                ))
            
            # Create a prompt for the AI to summarize the emails
            email_texts = "\n\n".join([
                f"Subject: {email.subject}\nFrom: {email.sender}\nContent: {email.content}"
                for email in truncated_emails
            ])
            
            summary_prompt = f"""Please provide a concise summary (less than 500 words) of these {len(emails)} emails:

{email_texts}

Focus on the key points and most important information."""
            
            logger.info("Getting AI summary of emails")
            try:
                summary = self._get_ai_response(summary_prompt)
                logger.info("Received AI summary")
            except ValueError as e:
                logger.error(f"Error getting AI summary: {str(e)}")
                raise
            
            return EmailSummary(
                total_emails=len(emails),
                unread_count=len([e for e in emails if not e.is_read]),
                recent_emails=emails,  # Use original emails for display
                summary=summary
            )
        except Exception as e:
            logger.error(f"Error in summarize_emails: {str(e)}", exc_info=True)
            raise
    
    def send_email(self, to: str, subject: str, content: str) -> bool:
        """Send an email with AI assistance."""
        try:
            logger.info(f"Starting email send process to: {to}")
            logger.info(f"Email subject: {subject}")
            logger.info(f"Content length: {len(content)} characters")
            
            # Let AI review the email before sending
            review_prompt = f"Please review this email:\nTo: {to}\nSubject: {subject}\nContent: {content}\n\nIs this appropriate to send?"
            logger.info("Getting AI review of email")
            try:
                review = self._get_ai_response(review_prompt)
                logger.info(f"AI review received: {review}")
            except Exception as e:
                logger.error(f"Error getting AI review: {str(e)}")
                return False
            
            self.console.print(Markdown(review))
            
            user_choice = Prompt.ask("Would you like to send this email?", choices=["y", "n"])
            logger.info(f"User choice for sending email: {user_choice}")
            
            if user_choice == "y":
                logger.info("User confirmed sending email")
                try:
                    result = self.tools.gmail.create_email(to, subject, content)
                    if result:
                        logger.info("Email sent successfully")
                    else:
                        logger.error("Failed to send email - create_email returned False")
                    return result
                except Exception as e:
                    logger.error(f"Error in Gmail API call: {str(e)}", exc_info=True)
                    return False
            else:
                logger.info("User cancelled email send")
                return False
                
        except Exception as e:
            logger.error(f"Error in send_email: {str(e)}", exc_info=True)
            return False
    
    def get_specific_email(self, email_id: str) -> Optional[Email]:
        """Get a specific email by ID."""
        try:
            logger.info(f"Attempting to retrieve email with ID: {email_id}")
            
            try:
                email = self.tools.gmail.get_email(email_id)
                if email:
                    logger.info(f"Successfully retrieved email: {email.subject}")
                    logger.info(f"Email details - From: {email.sender}, To: {email.recipient}")
                    logger.info(f"Email timestamp: {email.timestamp}")
                    logger.info(f"Email read status: {email.is_read}")
                    return email
                else:
                    logger.warning(f"No email found with ID: {email_id}")
                    return None
            except Exception as e:
                logger.error(f"Error in Gmail API call: {str(e)}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"Error in get_specific_email: {str(e)}", exc_info=True)
            return None
    
    def run(self) -> None:
        """Run the interactive session."""
        self.console.print("[bold green]Welcome to the Calendar AI Agent![/bold green]")
        self.console.print("I can help you manage your emails and calendar through natural language commands.\n")
        
        self.console.print("[bold yellow]Email Commands:[/bold yellow]")
        self.console.print("• [cyan]Summarize emails:[/cyan]")
        self.console.print("  - 'Summarize my last 3 unread emails'")
        self.console.print("  - 'What's in my inbox?'")
        self.console.print("  - 'Show me my recent emails'")
        
        self.console.print("\n• [cyan]Send emails:[/cyan]")
        self.console.print("  - 'Send an email to john@example.com about the project update'")
        self.console.print("  - 'Write to the team about the meeting tomorrow'")
        self.console.print("  - 'Compose an email to HR about vacation request'")
        
        self.console.print("\n• [cyan]Get specific emails:[/cyan]")
        self.console.print("  - 'Get email with ID abc123'")
        self.console.print("  - 'Show me the email about the project deadline'")
        
        self.console.print("\n[bold yellow]Calendar Commands:[/bold yellow]")
        self.console.print("• [cyan]Schedule events:[/cyan]")
        self.console.print("  - 'Schedule a meeting tomorrow at 2 PM'")
        self.console.print("  - 'Create a 1-hour event for team sync'")
        self.console.print("  - 'Book a meeting with the client next week'")
        
        self.console.print("\n• [cyan]View calendar:[/cyan]")
        self.console.print("  - 'What's on my calendar for next week?'")
        self.console.print("  - 'Show my upcoming meetings'")
        self.console.print("  - 'List my events for tomorrow'")
        
        self.console.print("\n• [cyan]Check availability:[/cyan]")
        self.console.print("  - 'When am I free tomorrow?'")
        self.console.print("  - 'Find a 30-minute slot for a meeting'")
        self.console.print("  - 'What's my availability next week?'")
        
        self.console.print("\n[bold red]Type 'exit' to quit.[/bold red]\n")
        
        while True:
            try:
                user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
                
                if user_input.lower() == 'exit':
                    self.console.print("[bold green]Goodbye![/bold green]")
                    break
                
                # Add user message to conversation history
                self.conversation.add_message("user", user_input)
                
                # Process command and get response
                response = self._process_command(user_input)
                
                # Add AI response to conversation history
                self.conversation.add_message("assistant", response)
                
                # Display response
                self.console.print(Markdown(response))
                
            except KeyboardInterrupt:
                self.console.print("\n[bold green]Goodbye![/bold green]")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                self.console.print("[bold red]An error occurred. Please try again.[/bold red]")

if __name__ == "__main__":
    agent = CalendarAgent()
    agent.run() 