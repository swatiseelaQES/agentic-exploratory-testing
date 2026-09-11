# AI-enabled exploratory testing

A controlled experiment in which an OpenAI-powered agent explores a web application through Selenium. The agent receives a charter and current page observations, chooses one bounded action at a time, adapts based on evidence, and records its session.

## What is in the repo

- `dist/`: the intentionally imperfect shopping application under test
- `exploratory_agent/`: observation, planning, controlled execution, and reporting
- `charters/`: human-authored exploratory missions
- `known-defects/`: the hidden evaluation answer key; never sent to the model
- `sessions/`: generated screenshots, decisions, and reports

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and add your OpenAI API key.
4. In one terminal, run `python -m http.server 8000 --directory dist`.
5. In another terminal, run `python run_agent.py`.

The application can be reset by clearing site data for `localhost:8000`.

## Design boundary

OpenAI selects the next action using structured output. Selenium alone executes actions. The model cannot run arbitrary code, navigate outside `BASE_URL`, access the answer key, or bypass the action vocabulary.

## Current MVP limitations

- Findings are preserved in the exploration log but are not yet promoted through a formal suspicion → investigation → reproduced-defect lifecycle.
- Page observation is text and accessibility-oriented; screenshot vision is planned for a later phase.
- The initial report is a trace, not yet a polished defect report.

