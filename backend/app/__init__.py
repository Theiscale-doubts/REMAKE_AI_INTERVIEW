"""VoxHire backend package.

Layout:
    app/main.py     FastAPI application, HTTP routes, request/response models
    app/agent.py    interview engine — domains, prompts, adaptive difficulty
    app/storage.py  durable storage — CSV mirror and the Google Sheets record
"""
