# AGENTS.md

# Project

Profilytix is a local Windows desktop application for small business financial analytics.

# Core Rules

- Use Python 3.12+.
- Use PySide6 for desktop UI.
- Use pandas for ExcelCSV processing.
- Use scikit-learn for classical ML.
- Do not create a web application.
- Do not use FastAPI, Flask, Django, React, Next.js, or any web stack.
- Do not add authentication.
- Do not add payments.
- Do not add cloud infrastructure.
- Do not add a database in MVP unless explicitly requested.
- Do not use LLM API in the first version.
- Keep architecture simple.
- Prefer readable code over clever abstractions.
- Every task must preserve existing working functionality.

# Run Commands

Install dependencies

```bash
pip install -r requirements.txt
```

# Instruction Change Rule

If a future task appears to require violating, bypassing, or changing any instruction in
`PROJECT_CONTEXT.md` or `AGENTS.md`, stop and tell the user before making that change.
Discuss the tradeoff first, especially for changes to the technology stack, application
type, storage model, cloud usage, authentication, payments, LLM/API usage, or MVP scope.
