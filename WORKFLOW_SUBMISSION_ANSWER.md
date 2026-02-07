# Answer: Does Data Get Saved When Clicking "Save"?

## Question Summary
You asked whether clicking the "save" button in your EnterVehicle workflow actually saves the user-entered data (name, phone, vehicle info, etc.), because you don't see the saved data.

## Short Answer
**Previously: NO** - The system only saved workflow **definitions** (the structure/template), not the actual user-entered data.

**Now: YES** - After the changes made in this PR, the system can now save user-entered workflow execution data when properly implemented in your client application.

## What Was Missing

### Before This PR
The system had:
- ✅ Ability to create and save workflow **definitions** (templates with card types and configurations)
- ✅ Button card with `action_type: "submit"` configuration
- ❌ NO backend endpoint to receive and save user-entered form data
- ❌ NO database model to store workflow execution submissions

This meant that when a user clicked "save", there was **nowhere for the data to go**.

### After This PR
The system now has:
- ✅ New `WorkflowSubmission` database model to store user-entered data
- ✅ New API endpoint: `POST /api/v1/workflow/<workflow_id>/submit/`
- ✅ New API endpoint: `GET /api/v1/workflow/<workflow_id>/submissions/` to retrieve saved data
- ✅ Full test coverage for submission functionality
- ✅ Documentation and integration examples

## How to Use the New Feature

### 1. Your Workflow Definition (Already Done)
Your EnterVehicle workflow JSON defines the structure:
```json
{
  "name": "EnterVehicle",
  "status": "published",
  "definition": {
    "steps": [
      {
        "id": "id_card_0yebms",
        "type": "id_card",
        "props": { ... }
      },
      {
        "id": "name_card_ops1oy",
        "type": "name_card",
        "props": { ... }
      },
      {
        "id": "vehicle_card_8rx28t",
        "type": "vehicle_card",
        "props": { ... }
      },
      ...
      {
        "id": "button_card_ng5k3p",
        "type": "button_card",
        "props": {
          "button_text": "save",
          "action_type": "submit"  // Changed to "submit" to save data
        }
      }
    ]
  }
}
```

**Important:** Change your button's `action_type` from `"next"` to `"submit"` if you want it to save data to the server.

### 2. Implement Data Submission in Your Client

When the user clicks the "save" button, your client application (web, Android, etc.) should:

**A. Collect all form data**
```javascript
const formData = {
  "id_card_0yebms": {
    "id_number": "None",
    "full_name": "Alice Brown Test",
    "gender": "Female"
  },
  "name_card_ops1oy": "Alice Brown Test",
  "vehicle_card_8rx28t": {
    "number_plate": "ALICEB1",
    "make_model": "BikeCo BMX",
    "color": "Green"
  },
  "phone_card_c252wi": "+1234567890",
  "company_card_cgb0r3": "Global Transport Inc."
};
```

**B. Send POST request to submission endpoint**
```javascript
const response = await fetch('/api/v1/workflow/681cfba8-59bb-4c31-af89-6756802a46f8/submit/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    data: formData,
    submitted_by: "alice@example.com",  // Optional
    session_id: "session_123"  // Optional
  })
});

const result = await response.json();
// result.id = unique submission ID
// result.message = "Workflow data submitted successfully."
```

### 3. View Saved Data

**Option A: Via API**
```javascript
const response = await fetch('/api/v1/workflow/681cfba8-59bb-4c31-af89-6756802a46f8/submissions/');
const data = await response.json();

// data.results contains all submissions
data.results.forEach(submission => {
  console.log(submission.submission_data);  // The user-entered data
  console.log(submission.submitted_at);     // When it was submitted
  console.log(submission.submitted_by);     // Who submitted it
});
```

**Option B: Via Django Admin Panel**
1. Log into Django admin at `/admin/`
2. Go to "Workflow submissions"
3. View all submitted data with filtering and search

## Why You Weren't Seeing Saved Data

1. **No Backend Implementation**: The button was configured with `action_type: "next"` instead of `"submit"`, and even if it was "submit", there was no backend endpoint to receive the data.

2. **Client Not Sending Data**: Your client application (whether web or Android) needs to be programmed to collect the form data and send it to the submission endpoint when the button is clicked.

3. **Workflow Definition vs. Execution Data**: The system was only storing workflow **templates** (the structure), not the actual **execution data** (what users entered).

## Action Items for You

To enable data saving in your application:

1. **Update your EnterVehicle workflow**:
   - Change button `action_type` from `"next"` to `"submit"`

2. **Run database migrations**:
   ```bash
   python manage.py migrate workflows
   ```

3. **Implement client-side submission logic**:
   - Add JavaScript/Android code to collect form data
   - Send POST request to `/api/v1/workflow/<workflow_id>/submit/` when save button is clicked
   - Handle the response (show success message, navigate to next screen, etc.)

4. **Test the flow**:
   - Fill out the form
   - Click save
   - Check `/api/v1/workflow/<workflow_id>/submissions/` to verify data was saved

## Example Complete Flow

```javascript
// 1. User fills out the form
// 2. User clicks "save" button
// 3. Your client code runs:

async function handleSaveButton(workflowId) {
  // Collect data from form fields
  const data = {
    "id_card_0yebms": {
      "id_number": document.getElementById('id_number').value,
      "full_name": document.getElementById('full_name').value,
      "gender": document.getElementById('gender').value
    },
    "name_card_ops1oy": document.getElementById('name_input').value,
    "vehicle_card_8rx28t": {
      "number_plate": document.getElementById('plate').value,
      "make_model": document.getElementById('make').value,
      "color": document.getElementById('color').value
    },
    "phone_card_c252wi": document.getElementById('phone').value,
    "company_card_cgb0r3": document.getElementById('company').value
  };

  try {
    const response = await fetch(`/api/v1/workflow/${workflowId}/submit/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data: data,
        submitted_by: getCurrentUser(),
        session_id: getSessionId()
      })
    });

    if (response.ok) {
      const result = await response.json();
      alert(`Data saved successfully! Submission ID: ${result.id}`);
      // Navigate to next screen or show confirmation
    } else {
      alert('Error saving data');
    }
  } catch (error) {
    console.error('Submission error:', error);
    alert('Network error - data not saved');
  }
}
```

## Summary

**The answer to your question**: The data was **NOT being saved** before because the backend functionality didn't exist. Now it **CAN be saved**, but you need to:
1. Update your workflow button to `action_type: "submit"`
2. Run migrations to create the database table
3. Implement client-side code to send the data when the button is clicked

The system now has everything needed to save and retrieve workflow execution data!
