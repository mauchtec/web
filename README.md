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

## Residence App API Contract

See [docs/RESIDENCE_APP_API_SCHEMA.md](docs/RESIDENCE_APP_API_SCHEMA.md) for the current GateCore API contract that the residence app should use.
The machine-readable spec is [docs/RESIDENCE_APP_API_OPENAPI.yaml](docs/RESIDENCE_APP_API_OPENAPI.yaml).

## How Android Will Consume
Android (or any client) fetches workflow JSON via API and renders it according to the schema. No backend changes needed for new clients.

## Example Workflow
See `workflows/tests/` or API output for a sample JSON workflow.

## Next Steps
- Implement component template system
- Add workflow validation layer
- Build web-based visual builder (frontend app)
- Add preview/simulation mode

## Face Device Sync

Some third-party facial-recognition devices connect back to the backend over WebSocket instead of plain REST.
Run the sync server on the port the device expects:

```bash
python manage.py run_face_sync_ws --host 0.0.0.0 --port 12391
```

That server answers the device's `getDeviceSettings`, `getUserInfo`, `addUser`, `delUser`, and `delMultiUser` commands using the current GateCore resident data and face photos.

---

*Write this before Phase 2, not after!*
