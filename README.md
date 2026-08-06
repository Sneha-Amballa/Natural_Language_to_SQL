# AI Text-to-SQL Agent

A production-grade AI Text-to-SQL Agent that converts natural language into executable SQL queries, validates and sanitizes them, executes them, and visualizes/explains the results.

## Folder Structure
* `agent/`: Orchestration and memory logic.
* `tools/`: Agent-callable tools.
* `core/`: Database connection, safety verification, and telemetry.
* `models/`: Unified Pydantic schema structures.
* `services/`: Downstream Groq API client interface adapters.
* `ui/`: Streamlit presentation panels.
* `utils/`: Common utilities (CSV import, visualizer selectors, parsers).
* `prompts/`: Versioned prompt templates.
* `tests/`: Project validation unit tests.

## Local Configuration
1. Initialize local virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate # Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment configuration:
   ```bash
   cp .env.example .env
   # Set GROQ_API_KEY in .env
   ```
4. Run application:
   ```bash
   streamlit run app.py
   ```
