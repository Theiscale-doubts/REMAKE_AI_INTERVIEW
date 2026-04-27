# Interview Agent Backend API

## Overview

This is a FastAPI-based backend for an AI-powered interview agent named **Synthia**. The agent conducts conversational interviews, asks follow-up questions, and saves question-answer pairs to a CSV file for later analysis.

## Architecture

The backend consists of three main components:

- **main.py**: FastAPI server with API endpoints
- **agent.py**: LangChain agent implementation with memory
- **tools.py**: Custom tools for the agent (CSV logging)

## Technology Stack

- **FastAPI**: Web framework for API endpoints
- **LangChain**: Framework for building the conversational agent
- **Google Generative AI**: LLM provider (Gemini 2.5 Flash)
- **Python 3.10+**: Required for union type syntax (`str | None`)

## Setup

### Prerequisites

1. Python 3.10 or higher
2. Google API key for Generative AI

### Installation

```bash
# Install dependencies
pip install fastapi uvicorn langchain langchain-google-genai python-dotenv

# Create .env file
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

### Running the Server

```bash
# Method 1: Using uvicorn directly
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Method 2: Using python
python main.py
```

The server will start at `http://127.0.0.1:8000`

---

## API Endpoints

### 1. Start Session

**Endpoint:** `GET /api/start`

**Description:** Initializes a new interview session and returns a unique session ID.

**Request:** None

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Usage:**
- Call this endpoint before starting an interview
- Store the returned `session_id` for all subsequent chat requests
- Each session maintains its own conversation history

**Example:**
```bash
curl -X GET http://127.0.0.1:8000/api/start
```

---

### 2. Chat with Agent

**Endpoint:** `POST /api/chat`

**Description:** Sends a user message to the interview agent and receives the agent's response (next question).

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Hi, I'm John. I'm a software engineer with 5 years of experience."
}
```

**Response:**
```json
{
  "question": "That's great, John! Tell me about your most challenging project in those 5 years."
}
```

**Behavior:**

**First Message (Empty History):**
- Treats the message as an introduction
- Does NOT call any tools
- Greets the user and asks the first interview question

**Subsequent Messages:**
- Treats the last AI message as the question
- Treats the current user message as the answer
- Automatically calls `save_qa_tool` to log the Q&A pair
- Generates one thoughtful follow-up question

**Error Response:**
```json
{
  "detail": "Error message here"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Hello, I am interested in the position"
  }'
```

---

### 3. Save Q&A Pair

**Endpoint:** `POST /api/save`

**Description:** Manually saves a question-answer pair to the interview log CSV file. This is useful for frontend-initiated saves or manual logging.

**Request Body:**
```json
{
  "question": "What is your biggest strength?",
  "answer": "I am a quick learner and adapt well to new technologies.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters:**
- `question` (string, required): The interview question
- `answer` (string, required): The candidate's answer
- `session_id` (string, optional): Session identifier for tracking

**Response:**
```json
{
  "status": "ok",
  "detail": "Q&A pair saved successfully."
}
```

**Special Cases:**
- If the same Q&A pair was just saved, returns: `"Duplicate Q&A skipped."`
- Creates `interview_log.csv` if it doesn't exist
- Automatically adds headers on first write

**CSV Output Format:**
```csv
Question,Answer
"What is your biggest strength?","I am a quick learner and adapt well to new technologies."
```

**Error Response:**
```json
{
  "detail": "Error message here"
}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8000/api/save \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What motivates you?",
    "answer": "I love solving complex problems.",
    "session_id": "abc123"
  }'
```

---

## Agent Behavior

### Synthia - The Interview Agent

**Personality:** Expert interviewer who conducts thoughtful, conversational interviews

**Workflow:**

1. **Initial Contact:**
   - User introduces themselves
   - Agent greets and asks first question
   - No data saved yet

2. **Interview Loop:**
   - User answers previous question
   - Agent automatically saves Q&A pair to CSV
   - Agent generates relevant follow-up question
   - Repeat

3. **Memory Management:**
   - Each session maintains independent conversation history
   - History stored in-memory (not persistent across server restarts)
   - Agent has context of entire conversation

### LLM Configuration

- **Model:** Google Gemini 2.5 Flash
- **Temperature:** 0.7 (balanced creativity and coherence)
- **Tools:** save_qa_tool (automatic CSV logging)

---

## Data Storage

### Interview Log CSV

**Location:** `interview_log.csv` (same directory as `tools.py`)

**Format:**
```csv
Question,Answer
"Question 1","Answer 1"
"Question 2","Answer 2"
```

**Features:**
- Automatic header creation
- Duplicate detection (prevents consecutive identical entries)
- UTF-8 encoding
- Append-only mode (preserves all historical data)

---

## CORS Configuration

The API is configured to allow cross-origin requests from any origin:

```python
allow_origins=["*"]  # For development only
```

**Production Recommendation:** Restrict to specific domains:
```python
allow_origins=["https://yourdomain.com"]
```

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK:** Successful operation
- **500 Internal Server Error:** Server-side error with detail message

Errors include descriptive messages in the response body:
```json
{
  "detail": "Specific error description"
}
```

---

## Development Notes

### Session Management
- Sessions are stored in-memory and will be lost on server restart
- For production, consider using Redis or database-backed session storage

### Security Considerations
- No authentication implemented (add JWT or API keys for production)
- CORS is wide open (restrict in production)
- API key should be stored securely (use secrets manager in production)

### Scalability
- In-memory session storage limits horizontal scaling
- Consider external session store (Redis, PostgreSQL)
- CSV logging is not suitable for high-traffic scenarios

---

## Example Interview Flow

```bash
# 1. Start new session
curl -X GET http://127.0.0.1:8000/api/start
# Response: {"session_id": "abc-123"}

# 2. Send introduction
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123", "message": "Hi, I am Sarah."}'
# Response: {"question": "Hello Sarah! What position are you interested in?"}

# 3. Answer question (automatically saved)
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123", "message": "I am interested in the Senior Developer role."}'
# Response: {"question": "Great! What experience do you have with backend development?"}

# 4. Continue conversation...
```

---

## Troubleshooting

### Common Issues

**"GOOGLE_API_KEY not found"**
- Ensure `.env` file exists with valid API key
- Check that `python-dotenv` is installed

**"Module not found" errors**
- Install all required dependencies
- Verify Python version is 3.10+

**CSV file not created**
- Check write permissions in the application directory
- Verify the agent is calling `save_qa_tool` correctly

**Session not found**
- Sessions are cleared on server restart
- Ensure you're using the session_id from `/api/start`

---

## Future Enhancements

- [ ] Add authentication and authorization
- [ ] Implement persistent session storage
- [ ] Database-backed interview logs
- [ ] Export interview transcripts in multiple formats
- [ ] Add interview analytics and insights
- [ ] Support multiple interview templates
- [ ] Real-time WebSocket support for streaming responses

---

## License

This project is provided as-is for educational and development purposes.