# Next Module Dependency Analysis

## Current Dependency State

### Backend Dependencies (`pyproject.toml`)
The project utilizes Python >=3.9 with the following major packages:
- **Core HTTP & Routing:** `fastapi`, `uvicorn`, `httpx`
- **Validation & Models:** `pydantic>=2.5`
- **Data & Text Processing:** `PyMuPDF`, `lxml`, `spacy`, `nltk`
- **External AI:** `google-genai`
- **Testing:** `pytest`, `pytest-cov`

### Frontend Dependencies (`frontend/package.json`)
The frontend is built on Next.js 15.1.6 utilizing:
- `react`, `react-dom`
- `tailwindcss` (for styling)
- Built-in Next.js routing

## Dependency Constraints for Future Modules

1. **Environmental Containment (Critical):**
   - No dependency may write hardcoded paths to `C:\Users\...` or `AppData`.
   - Python modules relying on `tempfile` have been globally overridden in `conftest.py` to route to `D:\RM\.tmp`. Any new dependency introducing native binaries or hardcoded cache directories must be evaluated for containment breaches.

2. **No Mocks Allowed:**
   - Any new module must use the real, existing components (e.g., `QueryParser`, `QueryEngine`, `ReviewOrchestrator`).
   - Placeholder implementations are forbidden unless explicit approval is granted.

3. **None-Safe Contracts:**
   - Empty `CorpusGraph` or `CorpusManager` objects must be safely handled across all new module dependencies.
   - Core orchestrators must tolerate missing optional dependencies without catastrophic failure.
