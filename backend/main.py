import uuid
import os
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tools import extract_values
from agent import run_agent_turn
from tools import save_qa_tool, add_values
from groq import Groq


app = FastAPI()

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    domain: str | None = None

class InterviewResult(BaseModel):
    score: float
    feedback: str

class SaveRequest(BaseModel):
    question: str
    answer: str
    session_id: str | None = None,
    name: str | None = None,
    email: str | None = None,
    role: str | None = None,

@app.get("/api/check")
def start_chek():
    return {"session": " API is working fine"}
@app.get("/api/start")
def start_session():
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    try:
        print ("Received chat request:", request)
        agent_response = run_agent_turn(
    message=request.message,
    session_id=request.session_id,
    domain=request.domain
)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"question": agent_response}


@app.post("/api/save")
def save_endpoint(request: SaveRequest):
    """Save a question/answer pair to the interview log via tools.save_qa_tool.

    This endpoint is provided so the frontend can explicitly persist QA pairs.
    """
    try:
        result = save_qa_tool(request.question, request.answer, request.session_id, request.name, request.email, request.role)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "detail": result}

@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio using Groq Whisper."""
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    client = Groq(api_key=groq_api_key)
    audio_bytes = await file.read()
    try:
        transcription = client.audio.transcriptions.create(
            file=(file.filename or "audio.webm", audio_bytes),
            model="whisper-large-v3-turbo",
            language="en",
        )
        return {"transcript": transcription.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/api/log/{session_id}")
async def get_interview_results(session_id: str) -> InterviewResult:
    '''Generate interview evaluation using Groq LLM based on the interview log.'''
    Groq_api_key = os.getenv("GROQ_API_KEY")
    log_str = extract_values(session_id_to_find=session_id)
    print("Extracted log:", log_str)
    
    try:
        log = json.loads(log_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse interview log.")

    if not log:
        raise HTTPException(status_code=404, detail="Interview log not found or is empty.")

    first_entry = log[0]
    transcript = f"""
        Interview for: {first_entry.get('Role', 'N/A')}
        Candidate: {first_entry.get('Name', 'N/A')} ({first_entry.get('Email', 'N/A')})

        Questions and Answers:
    """
    for idx, qa in enumerate(log, 1):
        transcript += f"\nQ{idx}: {qa.get('Question', 'N/A')}\n"
        transcript += f"A{idx}: {qa.get('Answer', 'N/A')}\n"
    
    prompt = f"""You are an expert technical interviewer evaluating a candidate's interview performance.

{transcript}

Provide a concise evaluation in the following format:

SCORE: [number between 0-10 with one decimal, e.g., 7.5]

FEEDBACK:

## Overall Performance
[2-3 sentences summarizing the candidate's performance]

## Strengths
- [Strength 1]
- [Strength 2]
- [Strength 3]

## Areas for Improvement
- [Specific actionable improvement 1]
- [Specific actionable improvement 2]
- [Specific actionable improvement 3]

## Communication ([score out of 100]%)
[1-2 sentences on clarity, articulation, and engagement]

## Technical Knowledge ([score out of 100]%)
[1-2 sentences on depth and accuracy of technical understanding]

## Problem-Solving ([score out of 100]%)
[1-2 sentences on approach and methodology]

EVALUATION GUIDELINES:
- SCORE: Provide an overall score between 0-10 with one decimal place based on complete performance.
- PERCENTAGES: Assign individual scores out of 100 for each category independently. Each percentage represents absolute performance in that specific area:
  * 90-100%: Exceptional performance, demonstrates mastery
  * 80-89%: Strong performance, shows solid competency
  * 70-79%: Good performance, meets expectations
  * 60-69%: Adequate performance, room for improvement
  * 50-59%: Below expectations, needs significant improvement
  * Below 50%: Poor performance, major gaps identified
- Be STRICT and CRITICAL in your evaluation. Do not inflate scores.
- Reference specific examples from the transcript to justify each score.
- Scores should reflect actual demonstrated capability, not potential.
- Keep each section brief and actionable. Use bullet points for lists. Be direct and constructive.
"""
    
    client = Groq(api_key=Groq_api_key)

    try:
        message = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse the response
        response_text = message.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get response from Groq: {e}")

    
    # Extract score and feedback
    score = extract_score(response_text)
    feedback = extract_feedback(response_text)
    add_values(["Evaluation", f"Score: {score}", f"Feedback: {feedback}"], username="Interview")
    return InterviewResult(score=score, feedback=feedback)

def extract_score(response: str) -> float:
    """Extract the score from the LLM's response."""
    import re
    
    score_match = re.search(r'SCORE:\s*(\d+\.?\d*)', response, re.IGNORECASE)
    
    if score_match:
        try:
            score = float(score_match.group(1))
            return min(max(score, 0), 10)
        except (ValueError, IndexError):
            pass
    
    fallback_match = re.search(r'(\d+\.?\d*)\s*/\s*10', response)
    if fallback_match:
        try:
            return float(fallback_match.group(1))
        except (ValueError, IndexError):
            pass
    
    return 7.0

def extract_feedback(response: str) -> str:
    """Extract the feedback section from the LLM's response."""
    import re
    
    feedback_match = re.search(r'FEEDBACK:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
    
    if feedback_match:
        return feedback_match.group(1).strip()
    
    score_match = re.search(r'SCORE:\s*\d+\.?\d*', response, re.IGNORECASE)
    if score_match:
        return response[score_match.end():].strip()
    
    return response.strip()

    
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
