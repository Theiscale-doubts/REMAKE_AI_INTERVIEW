import dotenv
import os as _os
dotenv.load_dotenv(_os.path.join(_os.path.dirname(__file__), ".env"))
from typing import Dict
import random
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI

# Initialize LLM model instance with HIGHER temperature for more variety
google_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.9,
)
groq_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.9,
)
session_domains = {}
session_topics_covered = {}  # NEW: Track covered topics per session
session_question_count = {}  # NEW: Track question count

# Session store for histories
session_store: Dict[str, InMemoryChatMessageHistory] = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = InMemoryChatMessageHistory()
    return session_store[session_id]

# Domain-specific question banks with topic tags
DOMAIN_QUESTIONS = {
    "datascience": {
        "topics": [
            "Statistics (distributions, hypothesis testing, p-values, confidence intervals, correlation vs causation)",
            "Machine Learning basics (supervised/unsupervised learning, model evaluation metrics)",
            "Feature engineering and selection techniques",
            "Data preprocessing (missing data, outliers, scaling/normalization)",
            "A/B testing and experimental design",
            "Model validation (cross-validation, overfitting/underfitting)",
            "Python concepts (pandas, numpy, scikit-learn - concepts only, NO code writing)",
            "Real-world ML scenarios (deployment, algorithm selection)"
        ],
        "sample_starters": [
            "Explain the difference between Type I and Type II errors",
            "How do you evaluate a classification model's performance?",
            "What techniques would you use for feature selection?",
            "How do you handle missing data in a dataset?",
            "Explain the concept of overfitting and how to prevent it",
            "What's the difference between correlation and causation?",
            "How would you design an A/B test for a new feature?"
        ]
    },
    "hr(humain recourse) + managerial": {
        "topics": [
            "Self-introduction and professional background (walk me through your resume, career journey)",
            "Strengths (top strengths, what you excel at, how they add value)",
            "Weaknesses and self-improvement (honest weakness, steps taken to improve)",
            "Career goals and aspirations (short-term and long-term goals, where you see yourself in 5 years)",
            "Motivation and work values (what drives you, what kind of work energizes you)",
            "Why this company and role (research on the company, alignment with values and mission)",
            "Teamwork and collaboration (working in teams, handling different personalities)",
            "Leadership and initiative (taking ownership, leading without authority, stepping up)",
            "Conflict resolution (handling disagreements with teammates or managers, staying professional)",
            "Handling pressure and deadlines (working under stress, managing multiple priorities)",
            "Achievements and accomplishments (proudest professional achievement, impact delivered)",
            "Adaptability and change management (adjusting to new environments, handling uncertainty)",
            "Communication skills (how you communicate upward and across teams)",
            "Failure and learnings (a time you failed, what you learned, how you bounced back)",
            "Cultural fit and work style (preferred work environment, collaboration style)",
            "Feedback and criticism (receiving constructive feedback, acting on it)",
            "Work-life balance and self-management (managing time, staying productive)",
            "Salary and career expectations (what you're looking for, negotiation mindset)"
        ],
        "sample_starters": [
            "Tell me about yourself and walk me through your professional journey",
            "What would you say are your top three strengths?",
            "What is one weakness you are actively working on improving?",
            "Where do you see yourself professionally in the next 3 to 5 years?",
            "What motivates you the most in your work?",
            "Why are you interested in this role and our company specifically?",
            "Describe a time you had to work closely with a difficult teammate. How did you handle it?",
            "Tell me about a time you took initiative without being asked",
            "Describe a situation where you disagreed with your manager. What did you do?",
            "How do you manage your work when you have multiple deadlines at the same time?",
            "What is your proudest professional achievement so far?",
            "Tell me about a time you had to adapt quickly to a major change at work",
            "Tell me about a time you failed at something. What did you learn from it?",
            "How do you prefer to receive feedback from your manager?",
            "Describe your ideal work environment and team culture",
            "How do you handle a situation where you strongly disagree with a team decision?",
            "Tell me about a time you went above and beyond what was expected of you",
            "How do you stay productive and maintain focus when working under pressure?"
        ]
    },
    "data_analytics": {
        "topics": [
            "SQL fundamentals (SELECT, WHERE, JOIN types, GROUP BY, aggregations)",
            "Advanced SQL (subqueries, CTEs, window functions, CASE statements, query optimization)",
            "Data visualization principles (chart selection, chart types for different data, color theory, accessibility)",
            "Dashboard design (layout, hierarchy, interactivity, KPI placement, dashboard vs report)",
            "Data storytelling (narrative structure, audience adaptation, actionable insights, executive communication)",
            "Business metrics and KPIs (CAC, churn rate, LTV, conversion rates, retention metrics)",
            "Funnel analysis (drop-off identification, conversion optimization, user journey mapping)",
            "A/B testing and experimentation (statistical significance, sample size, hypothesis testing)",
            "Data cleaning techniques (handling missing values, outlier detection, duplicate removal strategies)",
            "Data quality frameworks (accuracy, completeness, consistency, timeliness, validation checks)",
            "Excel concepts (formulas, pivot tables, VLOOKUP/XLOOKUP, conditional formatting, data analysis)",
            "Tableau concepts (calculated fields, parameters, filters, actions, LOD expressions)",
            "Power BI principles (DAX basics, relationships, data modeling, measures vs columns)",
            "Exploratory Data Analysis techniques (distributions, correlations, patterns, summary statistics)",
            "Statistical concepts for analysts (mean, median, mode, standard deviation, percentiles, variance)",
            "Data segmentation and cohort analysis",
            "Pandas concepts for data manipulation (DataFrames, filtering, grouping, merging - conceptual understanding ONLY, NO code writing)",
            "Data transformation principles (pivoting, melting, aggregating, reshaping)",
            "Reporting best practices (executive summaries, formatting, clarity, actionability)",
            "Stakeholder communication (translating technical findings, managing expectations, presenting insights)",
            "Data ethics and privacy (GDPR basics, PII handling, anonymization, responsible analytics)",
            "Data warehousing concepts (fact tables, dimension tables, star schema, snowflake schema)",
            "ETL/ELT pipeline concepts (data flow, transformations, loading strategies)",
            "Real-world business scenarios (e-commerce analytics, marketing attribution, product analytics, customer behavior)"
        ],
        "sample_starters": [
            "How do you choose the right visualization for different data types?",
            "Explain window functions in SQL and when you'd use them",
            "What KPIs would you track for an e-commerce website?",
            "How do you handle duplicate records in a dataset?",
            "Explain the difference between a dashboard and a report",
            "What's your approach to exploratory data analysis?",
            "How would you optimize a slow SQL query?",
            "When would you use a LEFT JOIN vs an INNER JOIN in SQL?",
            "How do you identify and handle outliers in your data?",
            "What metrics would you use to measure customer retention?",
            "Explain how you would present technical findings to non-technical stakeholders",
            "How do you ensure data quality in your analysis?",
            "What's the difference between a measure and a dimension in BI tools?",
            "Describe your process for cleaning a messy dataset",
            "How would you design a dashboard for executive leadership?",
            "What statistical concepts are most important for data analysts?",
            "How do you handle missing values in different scenarios?",
            "Explain the concept of a data warehouse and its components",
            "What's your approach to A/B test analysis?",
            "How would you explain customer lifetime value to a marketing team?"
        ]
    },
    "product": {
        "topics": [
            "Product strategy and roadmap planning",
            "User research and customer discovery",
            "Prioritization frameworks (RICE, MoSCoW, Kano)",
            "Feature definition and user stories",
            "Metrics and success measurement",
            "Stakeholder management",
            "A/B testing and experimentation",
            "Competitive analysis and market positioning"
        ],
        "sample_starters": [
            "How do you prioritize features on a product roadmap?",
            "Explain how you would conduct user research for a new feature",
            "What metrics would you use to measure product success?",
            "How do you handle conflicting stakeholder requirements?",
            "Describe the RICE prioritization framework",
            "How would you analyze a competitor's product?",
            "What's your approach to writing user stories?"
        ]
    },
    "frontend": {
        "topics": [
            "HTML/CSS fundamentals (box model, specificity, flexbox, grid)",
            "JavaScript core concepts (closures, event loop, promises, async/await)",
            "React concepts (virtual DOM, hooks, state management, component lifecycle)",
            "Browser performance (lazy loading, code splitting, rendering optimization)",
            "Accessibility (WCAG, ARIA, semantic HTML)",
            "Responsive design and media queries",
            "TypeScript fundamentals (types, interfaces, generics)",
            "Testing (unit tests, integration tests, testing-library)",
            "Web APIs (fetch, localStorage, service workers)",
            "Build tools and bundlers (Vite, Webpack concepts)"
        ],
        "sample_starters": [
            "Explain the difference between flexbox and CSS Grid",
            "What is the JavaScript event loop and how does it work?",
            "How do React hooks differ from class component lifecycle methods?",
            "What strategies do you use to improve frontend performance?",
            "Explain the concept of closures in JavaScript",
            "How would you make a web application accessible?",
            "What is the difference between == and === in JavaScript?",
            "How does the virtual DOM work in React?",
            "What is TypeScript and why would you use it over JavaScript?",
            "How do you handle state management in a large React application?"
        ]
    },
    "devops": {
        "topics": [
            "CI/CD pipelines (build, test, deploy stages)",
            "Containerization (Docker concepts, images, containers, volumes)",
            "Container orchestration (Kubernetes basics, pods, services, deployments)",
            "Infrastructure as Code (Terraform, Ansible concepts)",
            "Cloud platforms (AWS/GCP/Azure core services)",
            "Monitoring and observability (metrics, logs, traces, alerting)",
            "Linux fundamentals (processes, networking, file permissions)",
            "Networking concepts (DNS, TCP/IP, load balancers, reverse proxies)",
            "Security practices (secrets management, least privilege, vulnerability scanning)",
            "Incident response and on-call practices"
        ],
        "sample_starters": [
            "Explain the difference between a container and a virtual machine",
            "What is CI/CD and how would you design a pipeline for a web app?",
            "How does Kubernetes manage container scheduling?",
            "What is Infrastructure as Code and why is it important?",
            "How would you monitor a production application?",
            "Explain how DNS resolution works",
            "What is a reverse proxy and when would you use one?",
            "How do you manage secrets in a cloud environment?",
            "What would you do if a deployment caused production to go down?",
            "Explain the difference between horizontal and vertical scaling"
        ]
    }
}

SYSTEM_PROMPT = """
You are Synthia, an expert interviewer conducting a {total_questions}-question interview.

Current question: {current_question} of {total_questions}
Topics already covered: {covered_topics}

Domain context:
{domain_context}

Topic Rules:
- Never repeat or revisit a covered topic
- Pick questions from the domain topics list only — stay strictly on topic
- Start with broader, introductory questions and gradually go deeper
- Rotate across different topic areas — do not cluster similar topics together

Question Style:
- One focused question per turn, 1–2 sentences max
- Mix behavioral and situational questions naturally
- For HR: use real-world scenarios and STAR-style prompts (Situation, Task, Action, Result)
- For technical domains: concepts only, no code writing

Response Format:
- Brief evaluation of their previous answer (skip on Q1)
- One new question from an uncovered topic

Language: English only.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])
google_agent = prompt | google_llm
groq_agent = prompt | groq_llm

# Wrap with memory/history
google_agent_with_memory = RunnableWithMessageHistory(
    google_agent,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

groq_agent_with_memory = RunnableWithMessageHistory(
    groq_agent,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)
def safe_invoke_agent(payload, session_id):
    try:
        # Try Google first
        return google_agent_with_memory.invoke(
            payload,
            config={"configurable": {"session_id": session_id}}
        )
    
    except Exception as e:
        error_msg = str(e).lower()
        
        # Detect rate limit / quota errors
        if any(k in error_msg for k in [
            "quota", "rate limit", "resource exhausted", "429"
        ]):
            print("⚠️ Google LLM limit exceeded. Switching to Groq...")
            
            return groq_agent_with_memory.invoke(
                payload,
                config={"configurable": {"session_id": session_id}}
            )
        
        # If it's some other error, raise it
        raise e


_DOMAIN_ALIASES = {
    "data analytics": "data_analytics",
    "data_analytics": "data_analytics",
    "datascience": "datascience",
    "data science": "datascience",
    "frontend": "frontend",
    "front-end": "frontend",
    "front end": "frontend",
    "product": "product",
    "devops": "devops",
    "dev ops": "devops",
    "hr": "hr(humain recourse) + managerial",
    "hr / managerial": "hr(humain recourse) + managerial",
    "hr(humain recourse) + managerial": "hr(humain recourse) + managerial",
}

def _normalize_domain(domain: str) -> str:
    return _DOMAIN_ALIASES.get(domain.lower().strip(), domain.lower().strip())

def run_agent_turn(message: str, session_id: str, domain: str | None = None):
    # Initialize session tracking
    if session_id not in session_domains and domain:
        session_domains[session_id] = _normalize_domain(domain)
        session_topics_covered[session_id] = []
        session_question_count[session_id] = 0

    # Get domain for this session
    domain_text = session_domains.get(session_id, "general")
    print("Domain for session:", domain_text)

    # Increment question count
    session_question_count[session_id] += 1
    current_q = session_question_count[session_id]

    # Get domain-specific context
    domain_info = DOMAIN_QUESTIONS.get(domain_text, {})
    topics_list = domain_info.get("topics", [])
    
    # Build domain context with available topics
    domain_context = f"AVAILABLE TOPICS FOR {domain_text.upper()}:\n"
    for i, topic in enumerate(topics_list, 1):
        domain_context += f"{i}. {topic}\n"
    
    # Add some starter questions for inspiration (randomized)
    sample_starters = domain_info.get("sample_starters", [])
    if sample_starters:
        random_samples = random.sample(sample_starters, min(3, len(sample_starters)))
        domain_context += f"\nEXAMPLE QUESTIONS (for inspiration, vary your wording):\n"
        for sample in random_samples:
            domain_context += f"- {sample}\n"
    
    # Track covered topics
    covered = session_topics_covered.get(session_id, [])
    covered_str = ", ".join(covered) if covered else "None yet"
    
    # Create system prompt with session context
    system_prompt = SYSTEM_PROMPT.format(
        domain_context=domain_context,
        covered_topics=covered_str,
        current_question=current_q,
        total_questions="8-10"
    )
    
    system_prompt += f"\n\nSTRICT DOMAIN: {domain_text}. Ask ONLY {domain_text} questions. Ignore off-topic responses."
    
    result = safe_invoke_agent(
    {
        "input": message,
        "system_prompt": system_prompt
    },
    session_id=session_id
    )

    
    # Extract topic from result and add to covered topics (simple heuristic)
    # You might want to enhance this with more sophisticated topic extraction
    result_text = result.content.lower()
    for topic in topics_list:
        topic_keywords = topic.split('(')[0].strip().lower()
        if any(keyword in result_text for keyword in topic_keywords.split()):
            if topic not in covered:
                session_topics_covered[session_id].append(topic.split('(')[0].strip())
                break
    
    print(f"Question {current_q}: Covered topics so far: {session_topics_covered[session_id]}")
    
    return result.content
