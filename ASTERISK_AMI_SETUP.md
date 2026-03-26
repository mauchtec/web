# Asterisk AMI Integration Setup Guide

## What Was Implemented

✅ **AMI Connection** — Django now connects to Asterisk AMI on port 5038 and sends Originate actions  
✅ **Provider Call ID Capture** — Asterisk action_id is captured and stored as `VoipCall.provider_call_id`  
✅ **Call Status Tracking** — Real-time status updates from Asterisk events (ringing → answered → completed)  
✅ **Webhook Endpoint** — `/api/v1/voip/ami-event/` receives status updates from your Asterisk dialplan  
✅ **Database Fields** — `VoipCall.provider_call_id` and `VoipCall.call_status` now track Asterisk call lifecycle  
✅ **Tests** — 6 comprehensive webhook tests verify status updates work correctly  

## Required Configuration

Add these to your Django settings or `.env` file:

```python
# Asterisk AMI connection (server running voip originate calls)
ASTERISK_HOST = '192.168.0.x'              # Your Asterisk server IP
ASTERISK_AMI_PORT = 5038                   # Standard AMI port
ASTERISK_AMI_USER = 'admin'                # AMI username
ASTERISK_AMI_SECRET = 'admin'              # AMI secret/password
ASTERISK_TRUNK = 'PJSIP/trunk'             # SIP trunk name (e.g., PJSIP/your-trunk)
ASTERISK_CONTEXT = 'from-internal'         # Dialplan context for calls

# Webhook verification (optional but recommended)
VOIP_WEBHOOK_SECRET = 'your-secret-token'  # Token to verify webhook requests from Asterisk
```

## Asterisk Dialplan Configuration

Update your dialplan to send status updates back to Django. The webhook endpoint will receive the action_id/call_id and update the call status in real-time.

### Simple Method (Recommended)

If using the Asterisk script method, Django automatically stores the Django call_id in the database. Your dialplan should send this back:

```asterisk
; When call is placed
exten => s,n,Set(CALLID=<get_from_payload>)  ; Extract call_id from AstDB payload
exten => s,n,System(curl -s -X POST \
  http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=ringing&dial_status=" \
  -H "X-VoIP-Token: your-secret-token")

; Setup the call (Dial, etc.)
exten => s,n,Dial(SIP/destination@trunk)

; When call ends
exten => s,n,System(curl -s -X POST \
  http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=hangup&dial_status=${DIALSTATUS}" \
  -H "X-VoIP-Token: your-secret-token")
```

### How to Extract call_id from AstDB Payload

The Asterisk script stores the payload in AstDB under `intercom/${TOKEN}`:

```asterisk
; ${TOKEN} is passed as the extension name when originating: Local/${TOKEN}@intercom-trigger
; The dialplan can retrieve the payload like this:
exten => s,1,Set(PAYLOAD=${DB(intercom/${EXTEN})})
; PAYLOAD format: "target|call_id|resident_id|account_id|trunk"
; Extract the call_id (second field) using cut function
exten => s,n,Set(CALLID=${CUT(PAYLOAD,|,2)})
```

**Complete Example Using AstDB:**

```asterisk
[intercom-trigger]
exten => _.,1,NoOp(Received call for intercom token: ${EXTEN})
exten => _.,n,Set(PAYLOAD=${DB(intercom/${EXTEN})})
exten => _.,n,Set(CALLID=${CUT(PAYLOAD,|,2)})  ; Extract call_id
exten => _.,n,Set(TARGET=${CUT(PAYLOAD,|,1)})
exten => _.,n,Set(RESIDENT=${CUT(PAYLOAD,|,3)})
exten => _.,n,Set(TRUNK=${CUT(PAYLOAD,|,5)})

; Notify Django: ringing
exten => _.,n,System(curl -s -X POST \
  http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=ringing&dial_status=" \
  -H "X-VoIP-Token: your-secret-token")

; Place the actual call
exten => _.,n,Dial(${TRUNK}/${TARGET},30)

; Notify Django: call ended with status
exten => _.,n,System(curl -s -X POST \
  http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=hangup&dial_status=${DIALSTATUS}" \
  -H "X-VoIP-Token: your-secret-token")
exten => _.,n,Hangup()
```

### For AMI Users (Optional)

If you configure ASTERISK_HOST for direct AMI connection, Django will set `${CALLID}` variable and send `ActionID` instead:

```asterisk
exten => s,n,System(curl -s -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "action_id=${CALLID}&event=hangup&dial_status=${DIALSTATUS}")
```

Or without webhook secret:

```asterisk
exten => s,n,System(curl -s -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=hangup&dial_status=${DIALSTATUS}")
```

## How It Works Now

### Call Initiation Flow:
1. Android app POSTs to `/api/v1/voip/calls/` with `target` (phone number)
2. Django creates `VoipCall` record
3. Django connects to Asterisk AMI, sends Originate action → gets back `action_id`
4. Django stores `action_id` as `provider_call_id` and sets `call_status = "initiated"`
5. Returns to Android immediately with the call ID

### Call Status Updates:
1. Asterisk dialplan executes and calls endpoint at each status change (ringing, answered, hangup)
2. Webhook handler receives POST with `action_id`, `event`, and `dial_status`
3. Django matches `action_id` to `VoipCall.provider_call_id`
4. Updates `call_status` (ringing → answered → completed/no-answer/busy)
5. Android polls every 2 seconds and now sees real updates instead of empty string

### Expected Status Values:
- **"initiated"** — AMI Originate action sent successfully
- **"ringing"** — Phone is ringing (DIALBEGIN event)
- **"answered"** — Call was answered (ANSWER/DIALEND with DIALSTATUS=ANSWER)
- **"no-answer"** — Caller didn't answer (DIALSTATUS=NOANSWER)
- **"busy"** — Destination busy (DIALSTATUS=BUSY)
- **"completed"** — Call completed normally
- **"failed"** — Call failed to initiate

## Testing the Integration

### 1. Test Endpoint Availability:
```bash
curl -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "action_id=test-uuid&event=ringing&dial_status="
# Should return 404 (call not found) since test-uuid doesn't exist
```

### 2. Initiate a Test Call:
```bash
curl -X POST http://192.168.0.2:8000/api/v1/voip/calls/ \
  -H "Content-Type: application/json" \
  -d '{
    "resident": "unit-test",
    "target": "+27656231093",
    "account_id": 1
  }'
```

### 3. Check Django Logs:
```
[INFO] voip.tasks: VoIP initiate_sip_call: call_id=... target=... destination=... account_id=...
[INFO] voip.tasks: AMI originate success: action_id=... destination=...
```

### 4. Send Webhook Status Update:

For **Script Method** (using call_id):
```bash
curl -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=<the-call-id-from-step-2>&event=answered&dial_status=ANSWER"
```

For **AMI Method** (using action_id):
```bash
curl -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "action_id=<the-action-id-from-ami>&event=answered&dial_status=ANSWER"
```

### 5. Poll Call Status:
```bash
curl http://192.168.0.2:8000/api/v1/voip/calls/<call-id>/
# Should show: "call_status": "answered"
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `provider_call_id` stays empty | AMI not configured or unreachable | Verify `ASTERISK_HOST`, `ASTERISK_AMI_PORT`, credentials |
| `call_status` stays empty | Webhook not sending updates | Check Asterisk dialplan sends POST to webhook URL |
| 404 errors on webhook | `action_id` mismatch | Ensure dialplan sends same action_id that Django generated |
| Connection timeout | Asterisk not running or firewall blocking | Check `asterisk -rvvv`, test with `telnet $ASTERISK_HOST 5038` |

## Files Modified

- `voip/tasks.py` — Added `_initiate_asterisk_ami_call()` and integrated AMI into `initiate_sip_call()`
- `voip/views.py` — Added `ami_event_webhook()` endpoint
- `voip/urls.py` — Registered `/api/v1/voip/ami-event/` route
- `voip/tests/test_voip.py` — Added 6 AMI webhook tests

## Next Steps

1. **Configure `ASTERISK_HOST` and credentials** in Django settings
2. **Update your Asterisk dialplan** to POST webhook events
3. **Test with Asterisk CLI** — `core show calls` to see active calls
4. **Monitor logs** — `django.log` for any connection errors
5. **Call your test number** — Verify `provider_call_id` gets populated and `call_status` updates in real-time

Your Android app will now see real call status instead of polling forever with empty fields! 📱✅
