# AccessControll Project

## Overview
AccessControll is a Django-based backend and web app for visually designing, storing, and serving workflow definitions as JSON for Android and other clients.

### Features (Phase 1)
- Clean Django project structure
- Dedicated workflows app (separate from auth/users)
- Basic session authentication for testing
- Versioned API at `/api/v1/`
- Workflow model: id (UUID), name, description, version, status, created/updated, JSON definition
- **NEW: Workflow submission tracking** - Store and retrieve user-entered data from workflow executions
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

## API Endpoints

### Workflow Definition Endpoints
- `GET /api/v1/components/` - List all available workflow components
- `POST /api/v1/save/` - Create a new workflow definition
- `GET /api/v1/workflow/<uuid>/` - Fetch workflow definition by ID
- `PUT /api/v1/workflow/<uuid>/` - Update workflow definition
- `DELETE /api/v1/workflow/<uuid>/` - Delete workflow definition
- `POST /api/v1/workflow/<uuid>/` - Publish workflow (action: "publish")
- `POST /api/v1/preview/` - Generate HTML preview of workflow

### Workflow Submission Endpoints (NEW)
- `POST /api/v1/workflow/<uuid>/submit/` - Submit user-entered workflow execution data
- `GET /api/v1/workflow/<uuid>/submissions/` - List all submissions for a workflow (with pagination)

## Workflow Submission Feature

### Purpose
The workflow submission feature allows you to save user-entered data when someone completes a workflow. This is separate from the workflow definition itself.

### How It Works

1. **Define Your Workflow** - Create a workflow with input components (name_card, phone_card, vehicle_card, etc.)

2. **User Fills Out the Workflow** - User enters data in the form fields

3. **Submit the Data** - When the user clicks a button with `action_type: "submit"`, send a POST request to:
   ```
   POST /api/v1/workflow/<workflow_id>/submit/
   ```
   
   **Request Body:**
   ```json
   {
     "data": {
       "name_card_ops1oy": "Alice Brown Test",
       "phone_card_c252wi": "+1234567890",
       "vehicle_card_8rx28t": {
         "number_plate": "ALICEB1",
         "make_model": "BikeCo BMX",
         "color": "Green"
       }
     },
     "submitted_by": "alice@example.com",
     "session_id": "optional_session_id"
   }
   ```
   
   **Response:**
   ```json
   {
     "id": "submission-uuid",
     "workflow_id": "workflow-uuid",
     "message": "Workflow data submitted successfully.",
     "submitted_at": "2026-02-07T16:30:00Z"
   }
   ```

4. **Retrieve Submissions** - View all submitted data for a workflow:
   ```
   GET /api/v1/workflow/<workflow_id>/submissions/?page=1&per_page=20
   ```
   
   **Response:**
   ```json
   {
     "workflow_id": "workflow-uuid",
     "workflow_name": "EnterVehicle",
     "total_count": 5,
     "page": 1,
     "per_page": 20,
     "results": [
       {
         "id": "submission-uuid",
         "submission_data": { ... },
         "submitted_at": "2026-02-07T16:30:00Z",
         "submitted_by": "alice@example.com",
         "session_id": ""
       }
     ]
   }
   ```

### Button Card Action Types
- `next` - Navigate to next step (no submission)
- `submit` - Submit workflow data to server
- `back` - Go to previous step
- `cancel` - Cancel workflow
- `custom` - Custom action

### Integration Example

For your EnterVehicle workflow, when the user clicks the "save" button:

```javascript
// Collect data from all form fields
const formData = {
  "id_card_0yebms": {
    "id_number": document.getElementById('id_number').value,
    "full_name": document.getElementById('full_name').value,
    "gender": document.getElementById('gender').value
  },
  "name_card_ops1oy": document.getElementById('full_name_input').value,
  "vehicle_card_8rx28t": {
    "number_plate": document.getElementById('plate').value,
    "make_model": document.getElementById('make_model').value,
    "color": document.getElementById('color').value
  },
  "phone_card_c252wi": document.getElementById('phone').value,
  "company_card_cgb0r3": document.getElementById('company').value
};

// Submit to server
const response = await fetch(`/api/v1/workflow/${workflowId}/submit/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    data: formData,
    submitted_by: currentUser,
    session_id: sessionId
  })
});

const result = await response.json();
console.log('Submission saved:', result.id);
```

## How Android Will Consume
Android (or any client) fetches workflow JSON via API and renders it according to the schema. When the user completes the workflow, the app submits the data back to the server using the submission endpoint.

## Example Workflow
See `workflows/tests/` or API output for a sample JSON workflow.

## Next Steps
- Implement component template system ✅
- Add workflow validation layer
- Build web-based visual builder (frontend app) ✅
- Add preview/simulation mode ✅
- Add workflow submission tracking ✅
- Add workflow execution analytics

---

*Write this before Phase 2, not after!*
