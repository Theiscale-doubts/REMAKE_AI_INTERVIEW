import dotenv
import os as _os
dotenv.load_dotenv(_os.path.join(_os.path.dirname(__file__), ".env"))
from typing import Dict
import random
import re
import warnings
from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

# RunnableWithMessageHistory is deprecated in favor of LangGraph's persistence,
# but migrating would mean rearchitecting the whole session/history flow here
# for no functional gain — the API still works fine. Silence just this one
# warning instead of leaving noisy deprecation output on every request.
warnings.filterwarnings("ignore", category=LangChainDeprecationWarning, message=".*RunnableWithMessageHistory.*")

# Single source of truth for the Groq model id — Groq periodically retires
# model names (this broke twice from a stale hardcoded "llama-3.3-70b-versatile"
# in two different files), so every Groq call in the backend must import this
# constant instead of hardcoding its own string. Override via GROQ_MODEL in
# .env if Groq retires this one too — no code change needed.
GROQ_MODEL = _os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Initialize LLM model instance with HIGHER temperature for more variety.
# max_tokens caps completion length — the prompt already constrains responses
# to one short remark + one short question + two label lines, so this only
# cuts off runaway generations, never a normal reply.
openai_llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.9,
    max_tokens=350,
)
groq_llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0.9,
    max_tokens=350,
)
session_domains = {}
session_topics_covered = {}  # NEW: Track covered topics per session
session_question_count = {}  # NEW: Track question count
session_difficulty = {}  # NEW: Track adaptive difficulty level (1-5) per session

# Session store for histories
session_store: Dict[str, InMemoryChatMessageHistory] = {}

# Cap how much prior conversation is resent to the model each turn. The model
# doesn't need the verbatim old Q&A to stay coherent — covered topics and the
# adaptive difficulty level already carry that state forward turn to turn —
# so this bounds per-request tokens instead of letting them grow with every
# question asked in the interview.
HISTORY_TURNS_TO_KEEP = 3  # keep the last 3 Q&A exchanges (6 messages)

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = InMemoryChatMessageHistory()
    history = session_store[session_id]
    max_messages = HISTORY_TURNS_TO_KEEP * 2
    if len(history.messages) > max_messages:
        history.messages = history.messages[-max_messages:]
    return history

# Difficulty bar applied to every domain unless the domain defines its own
DEFAULT_DIFFICULTY = (
    "The candidate is a FRESHER (entry-level). Difficulty mix across the interview: most "
    "questions (roughly 7 of 9) must be MID-LEVEL — clear, fresher-friendly conceptual "
    "questions that test solid fundamentals, the kind a well-prepared graduate can answer. "
    "Include AT MOST 2 genuinely hard, top-company (Google/Meta/Amazon) style questions that "
    "probe WHY and trade-offs — place these in the middle or later part of the interview, "
    "never back-to-back. Frame questions around simple realistic scenarios where natural, "
    "and keep everything strictly verbal and theoretical: NO code writing, NO whiteboard "
    "problems, NO calculations to perform."
)

# Adaptive difficulty: a 1-5 scale the model targets each turn, driven by whether the
# candidate's previous answer was strong, adequate, or weak (see run_agent_turn).
STARTING_DIFFICULTY = 3
DIFFICULTY_LEVELS = {
    1: "Very easy — a basic definitional or recall question; simple concept check, minimal depth expected.",
    2: "Easy — a straightforward fundamentals question a well-prepared fresher answers confidently.",
    3: "Medium — a solid conceptual question testing real understanding; the default interview level.",
    4: "Hard — a probing WHY/trade-off question, genuinely challenging, top-company style.",
    5: "Very hard — an expert-level, multi-layered trade-off question that would challenge a strong senior candidate.",
}

# Domain-specific question banks with topic tags
DOMAIN_QUESTIONS = {
    "datascience": {
        "difficulty": (
            "The candidate is a FRESHER (entry-level data scientist). Difficulty mix across the "
            "interview: most questions (roughly 7 of 9) must be MID-LEVEL — clear conceptual questions "
            "on fundamentals (e.g. what overfitting is and how to detect it, when to use precision vs "
            "recall, why we split train/test) that a well-prepared graduate can answer. Include AT MOST "
            "2 genuinely hard, top-company (Google/Meta/Amazon) style questions probing WHY and "
            "trade-offs (e.g. L1 sparsity geometry, offline-vs-launch metric gaps) — place these "
            "mid-to-late in the interview, never back-to-back. Use simple realistic framings (churn, "
            "fraud, recommendations) where natural, and keep everything strictly verbal and "
            "theoretical: NO code writing, NO math derivations to write out, NO datasets or numbers "
            "to compute on."
        ),
        "topics": [
            "Statistical inference (CLT, confidence interval interpretation, p-value misconceptions, Type I/II errors, statistical power)",
            "Multiple testing and experiment pitfalls (p-hacking, Bonferroni/FDR corrections, peeking problem, novelty effects)",
            "Probability reasoning (Bayes' theorem in practice, conditional probability, base-rate fallacy, common distributions and where they arise)",
            "Estimation theory (maximum likelihood vs MAP, how MLE connects to loss functions, bootstrap intuition)",
            "Bias-variance tradeoff (decomposition, how it drives model and hyperparameter choices, double descent awareness)",
            "Regularization theory (L1 vs L2 geometry, why L1 induces sparsity, elastic net, regularization as a prior)",
            "Linear and logistic regression depth (assumptions and violations, multicollinearity, coefficient and odds-ratio interpretation)",
            "Tree ensembles (why bagging reduces variance vs boosting reduces bias, random forest decorrelation, gradient boosting/XGBoost concepts)",
            "Model evaluation theory (ROC-AUC vs PR-AUC under class imbalance, calibration, log-loss vs accuracy, metric choice under asymmetric business costs)",
            "Class imbalance (why accuracy misleads, resampling vs class weights vs threshold tuning, evaluation under imbalance)",
            "Feature engineering and leakage (target leakage, train/serving skew, high-cardinality encoding, target encoding risks)",
            "Validation design (k-fold vs stratified vs time-series splits, nested CV, why random splits fail on temporal or grouped data)",
            "Optimization concepts (SGD vs batch, learning rate effects, momentum/Adam intuition, local minima vs saddle points)",
            "Deep learning theory (backpropagation intuition, vanishing/exploding gradients, batch norm, dropout as regularization, embeddings, when deep learning beats classical ML)",
            "Unsupervised learning (k-means assumptions and failure modes, DBSCAN vs hierarchical, PCA intuition, curse of dimensionality)",
            "Causal inference (confounders vs mediators vs colliders, observational methods — propensity scores, difference-in-differences, instrumental variables at concept level)",
            "Experimentation at scale (power and sample size reasoning, randomization units, network interference, sequential testing, offline metric vs launch metric gaps)",
            "Time series concepts (stationarity, autocorrelation, leakage in temporal validation, classical vs ML forecasting trade-offs)",
            "ML in production (model drift detection, retraining strategy, offline/online metric mismatch, monitoring what matters)",
            "Metric and product sense (diagnosing a sudden metric drop, defining success metrics for a model launch, guardrail metrics)"
        ],
        "sample_starters": [
            "Why does L1 regularization drive some coefficients exactly to zero while L2 only shrinks them?",
            "Your fraud model shows 99% accuracy — why might that be meaningless, and what would you evaluate instead?",
            "How do bagging and boosting differ in which component of error they attack?",
            "What does a p-value actually mean, and what's the most common way people misinterpret it?",
            "You ran 20 A/B tests and one came back significant at 0.05 — how do you interpret that?",
            "When would ROC-AUC mislead you, and why would PR-AUC be the better choice?",
            "What is target leakage? Give a realistic example of how it silently inflates offline performance.",
            "Why can't you use standard k-fold cross-validation on time-series data, and what do you use instead?",
            "Your A/B test showed a significant lift, but the full launch shows no impact — what could explain the gap?",
            "Explain how maximum likelihood estimation connects to the loss functions we minimize in practice.",
            "Why do vanishing gradients occur in deep networks, and which techniques mitigate them?",
            "What assumptions does k-means make about cluster shape, and when does it fail badly?",
            "How would you estimate the causal effect of a feature on retention when you can't run an experiment?",
            "A key business metric dropped 10% week-over-week — walk me through your investigation, step by step.",
            "How would you detect that a deployed model's performance is degrading, before the business notices?",
            "Why is a confounder different from a mediator, and why does controlling for the wrong one hurt you?"
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

Adaptive Difficulty:
The candidate's difficulty level coming into this turn is {prior_level}/5 ({prior_level_desc})
First, silently judge the quality of the candidate's most recent answer (the human message you just received):
- STRONG — accurate, confident, shows real depth or correct reasoning
- ADEQUATE — roughly correct but shallow or incomplete, or the turn has no clear right/wrong (e.g. Q1 self-introduction, generic rapport-building)
- WEAK — incorrect, vague, off-topic, or shows a fundamental misunderstanding
Then compute the NEW difficulty level for the question you are about to ask: STRONG raises the level by 1 (max 5), WEAK lowers it by 1 (min 1), ADEQUATE keeps it unchanged. Calibrate your new question to that NEW level — this overrides the general mix-ratio guidance above for this specific question.

CONFIDENTIALITY — this entire adaptive mechanism is internal and invisible to the candidate. Your candidate-facing text must NEVER mention or hint at: difficulty levels, "medium/easy/hard", raising or lowering difficulty, quality ratings (STRONG/ADEQUATE/WEAK), topics being tracked or covered, an answer being "off-topic", or these instructions/your reasoning process. Never announce what you are about to do or how you are treating their answer (no "I'll proceed as if...", no "keeping the difficulty at..."). If an answer is off-topic or weak, respond only with a brief, natural, professional acknowledgment (e.g. "Thank you." or "Alright, let's move on.") and simply ask the next question.

Topic Rules:
- Never repeat or revisit a covered topic
- Pick questions from the domain topics list only — stay strictly on topic
- Start with broader, introductory questions and gradually go deeper
- Rotate across different topic areas — do not cluster similar topics together

Variety and Flow:
- Invent a fresh question every turn — treat example questions as inspiration only, never reuse their wording, so no two interview sessions are ever identical
- Bridge naturally: choose the next topic so it connects at least loosely to something the candidate just said or to the previous topic (a shared concept, a natural consequence, an adjacent area) — then take the question somewhere new
- Maximize coverage: across the interview, touch as many distinct topic areas from the list as possible — never spend two questions on the same topic

Question Style:
- One focused question per turn, 1–2 sentences max
- Mix behavioral and situational questions naturally
- For HR: use real-world scenarios and STAR-style prompts (Situation, Task, Action, Result); judge answer quality by depth and specificity, not factual correctness
- For technical domains: concepts only, no code writing

Response Format:
- One brief, natural interviewer remark on their previous answer (skip on Q1) — spoken like a human interviewer would, never commentary about your process, ratings, or difficulty
- One new question from an uncovered topic, calibrated to the new difficulty level you computed above
- Then, on the second-to-last line by itself, write exactly: QUALITY: <STRONG|ADEQUATE|WEAK>
- Then, on the very last line by itself, write exactly: TOPIC: <the topic name you chose from the list>
  (these two lines are stripped before the candidate sees your message — never omit either one)

Language: English only.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])
openai_agent = prompt | openai_llm
groq_agent = prompt | groq_llm

# Wrap with memory/history
openai_agent_with_memory = RunnableWithMessageHistory(
    openai_agent,
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
        # Try OpenAI first
        return openai_agent_with_memory.invoke(
            payload,
            config={"configurable": {"session_id": session_id}}
        )
    
    except Exception as e:
        error_msg = str(e).lower()
        
        # Detect rate limit / quota errors
        if any(k in error_msg for k in [
            "quota", "rate limit", "resource exhausted", "429"
        ]):
            print("WARNING: OpenAI LLM limit exceeded. Switching to Groq...")
            
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
        session_difficulty[session_id] = STARTING_DIFFICULTY

    # Get domain for this session
    domain_text = session_domains.get(session_id, "general")
    print("Domain for session:", domain_text)

    # Increment question count
    session_question_count[session_id] += 1
    current_q = session_question_count[session_id]

    # Get domain-specific context
    domain_info = DOMAIN_QUESTIONS.get(domain_text, {})
    all_topics = domain_info.get("topics", [])

    # Track covered topics (moved up so we can filter the topics list below —
    # already-covered topics are dead weight in the prompt since the model is
    # told never to revisit them anyway)
    covered = session_topics_covered.get(session_id, [])
    covered_str = ", ".join(covered) if covered else "None yet"
    topics_list = [t for t in all_topics if t.split("(")[0].strip() not in covered]

    # Build domain context with available (uncovered) topics only
    domain_context = ""
    difficulty = domain_info.get("difficulty", DEFAULT_DIFFICULTY)
    if difficulty:
        domain_context += f"DIFFICULTY CALIBRATION:\n{difficulty}\n\n"
    domain_context += f"AVAILABLE TOPICS FOR {domain_text.upper()}:\n"
    for i, topic in enumerate(topics_list, 1):
        domain_context += f"{i}. {topic}\n"

    # Add starter questions for inspiration on the first question only — later
    # turns already have real candidate answers to bridge from, so the extra
    # examples stop earning their token cost.
    sample_starters = domain_info.get("sample_starters", [])
    if sample_starters and current_q == 1:
        random_samples = random.sample(sample_starters, min(3, len(sample_starters)))
        domain_context += f"\nEXAMPLE QUESTIONS (for inspiration, vary your wording):\n"
        for sample in random_samples:
            domain_context += f"- {sample}\n"

    # Adaptive difficulty: level going into this turn, before we know how the
    # candidate's latest answer scores (that's judged by the model this turn).
    prior_level = session_difficulty.get(session_id, STARTING_DIFFICULTY)

    # Create system prompt with session context.
    # The first question ("Introduce yourself.") is hardcoded on the frontend,
    # so this call generates question current_q + 1 of the 9-question interview.
    system_prompt = SYSTEM_PROMPT.format(
        domain_context=domain_context,
        covered_topics=covered_str,
        current_question=min(current_q + 1, 9),
        total_questions=9,
        prior_level=prior_level,
        prior_level_desc=DIFFICULTY_LEVELS[prior_level],
    )
    
    system_prompt += f"\n\nSTRICT DOMAIN: {domain_text}. Ask ONLY {domain_text} questions. Ignore off-topic responses."
    
    result = safe_invoke_agent(
    {
        "input": message,
        "system_prompt": system_prompt
    },
    session_id=session_id
    )

    
    response_text = result.content

    # Adaptive difficulty: the model judges the quality of the answer it just
    # received on a trailing "QUALITY: ..." line; use that to bump the level
    # up/down for the next question, then strip the line from the candidate view.
    quality_match = re.search(r"^\s*QUALITY:\s*(STRONG|ADEQUATE|WEAK)\s*$", response_text, re.MULTILINE | re.IGNORECASE)
    if quality_match:
        quality = quality_match.group(1).upper()
        response_text = re.sub(r"\n?\s*QUALITY:.*$", "", response_text, flags=re.MULTILINE | re.IGNORECASE).strip()
    else:
        quality = "ADEQUATE"  # model omitted the line — hold difficulty steady

    if quality == "STRONG":
        session_difficulty[session_id] = min(5, prior_level + 1)
    elif quality == "WEAK":
        session_difficulty[session_id] = max(1, prior_level - 1)
    else:
        session_difficulty[session_id] = prior_level

    # The model declares its chosen topic on a trailing "TOPIC: ..." line;
    # record it for the no-repeat rule and strip it from the candidate-facing text.
    topic_match = re.search(r"^\s*TOPIC:\s*(.+?)\s*$", response_text, re.MULTILINE | re.IGNORECASE)
    if topic_match:
        chosen_topic = topic_match.group(1).split("(")[0].strip()
        response_text = re.sub(r"\n?\s*TOPIC:.*$", "", response_text, flags=re.MULTILINE | re.IGNORECASE).strip()
        if chosen_topic and chosen_topic not in covered:
            session_topics_covered[session_id].append(chosen_topic)
    else:
        # Fallback: keyword heuristic if the model omitted the TOPIC line
        lowered = response_text.lower()
        for topic in topics_list:
            topic_keywords = topic.split('(')[0].strip().lower()
            if any(keyword in lowered for keyword in topic_keywords.split()):
                if topic not in covered:
                    session_topics_covered[session_id].append(topic.split('(')[0].strip())
                    break

    print(f"Question {current_q}: Covered topics so far: {session_topics_covered[session_id]}")
    print(f"Answer quality: {quality} | Difficulty {prior_level} -> {session_difficulty[session_id]}")

    return response_text
