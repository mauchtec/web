# AccessControll Project

## Overview
AccessControll is a Django-based backend and web app for visually designing, storing, and serving workflow definitions as JSON for Android and other clients.

### Features (Phase 1)
- Clean Django project structure
- Dedicated workflows app (separate from auth/users)
- Basic session authentication for testing
- Versioned API at `/api/v1/`
- Workflow model: id (UUID), name, description, version, status, created/updated, JSON definition
- Ready for web-based visual builder (frontend app)

## Workflow Concept
A workflow is a sequence of steps/components, each defined by a JSON schema. Workflows are versioned and can be in draft or published state.

## Component System
Workflows are built from reusable components (e.g., text input, dropdown, yes/no, info display, approval, validation rule). Each component has a type, label, icon, description, form fields, and JSON generator.

## JSON Schema
Each workflow is stored as a single JSON definition. Example structure:
```json
{
  "id": "uuid",
  "name": "Sample Workflow",
  "version": "1.0.0",
  "status": "draft",
  "steps": [
    {"id": "step1", "type": "text_input", "config": {...}, "next": "step2"},
    {"id": "step2", "type": "approval", "config": {...}, "next": null}
  ]
}
```
- Deterministic, order-safe, human-readable
- No UI logic baked in

## API Endpoints (to be implemented)
- List workflows
- Fetch workflow by ID/version (returns pure JSON definition)

## How Android Will Consume
Android (or any client) fetches workflow JSON via API and renders it according to the schema. No backend changes needed for new clients.

## Example Workflow
See `workflows/tests/` or API output for a sample JSON workflow.

## Next Steps
- Implement component template system
- Add workflow validation layer
- Build web-based visual builder (frontend app)
- Add preview/simulation mode

---

*Write this before Phase 2, not after!*
