# Calendar AI Agent

An intelligent AI-powered assistant that helps manage your Gmail and Google Calendar through natural language commands.

## Features

### Email Management
- 📧 Summarize recent emails with AI-generated insights
- ✉️ Send emails with AI-assisted content review
- 🔍 Retrieve specific emails by ID
- 📊 Get overview of unread messages
- 📝 Smart email content analysis

### Calendar Management
- 📅 Create and schedule calendar events
- 📋 List upcoming events and meetings
- ⏰ Check calendar availability
- 👥 Manage event attendees
- 📍 Set event locations
- 📝 Add event descriptions

## Natural Language Commands

### Email Commands
- "Summarize my last 3 unread emails"
- "Send an email to john@example.com about the project update"
- "Get email with ID abc123"
- "What's in my inbox?"
- "Show me my recent emails"

### Calendar Commands
- "Schedule a meeting tomorrow at 2 PM"
- "What's on my calendar for next week?"
- "Create a 1-hour event for team sync"
- "When am I free tomorrow?"
- "Show my upcoming meetings"

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/calendar-agent.git
cd calendar-agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file with:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_CREDENTIALS=./credentials.json
```

5. Run the application:
```bash
python main.py
```

## Requirements

- Python 3.9+
- OpenAI API key
- Google Cloud Project with Gmail and Calendar APIs enabled
- Required Python packages (see requirements.txt)

## Usage

1. Start the agent:
```bash
python main.py
```

2. Type your request in natural language. Examples:
```
You: Summarize my last 5 unread emails
You: Schedule a meeting with the team tomorrow at 2 PM
You: What's on my calendar for next week?
```

3. The agent will:
   - Analyze your request
   - Execute the appropriate action
   - Provide a formatted response
   - For email sending, it will ask for confirmation before sending

## Features in Detail

### Email Features
- Smart email summarization with AI insights
- Natural language email composition
- Email content review before sending
- Detailed email retrieval
- Unread message tracking

### Calendar Features
- Natural language event creation
- Smart date and time parsing
- Availability checking
- Event details management
- Attendee handling

## Error Handling

The agent includes comprehensive error handling for:
- API rate limits
- Invalid date formats
- Missing required information
- Network issues
- Authentication errors

## Logging

Detailed logging is available in `calendar_agent.log` for debugging and monitoring.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 