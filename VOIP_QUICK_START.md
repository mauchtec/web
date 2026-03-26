# VoIP Webhook Implementation — Quick Start

## What's Fixed ✅

**Before:** provider_call_id and call_status stayed empty → Android app polled forever  
**After:** provider_call_id is automatically set → webhook updates call_status in real-time

## How to Implement (3 Steps)

### Step 1: Update Your Asterisk Dialplan

Add these two `System()` calls to your dialplan where calls are routed:

```asterisk
[your-dialplan-context]
exten => s,1,NoOp(Received call)
exten => s,n,Set(CALLID=${DB(intercom/${EXTEN})})  ; Extract from AstDB (use your logic)
exten => s,n,System(curl -s -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=ringing&dial_status=")
exten => s,n,Dial(SIP/destination@trunk)
exten => s,n,System(curl -s -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
  -d "call_id=${CALLID}&event=hangup&dial_status=${DIALSTATUS}")
exten => s,n,Hangup()
```

**Key points:**
- `${CALLID}` = the Django call_id (comes from your call origination)
- First webhook: sent when call starts ringing
- Second webhook: sent when call ends with `${DIALSTATUS}` (ANSWER, NOANSWER, BUSY, etc.)
- IP `192.168.0.2` = your Django server IP

### Step 2: Extract call_id from Your Storage

The script stores call_id in Asterisk. You need to retrieve it. Common methods:

**Option A: From AstDB (if using voip_originate_call.sh script)**
```asterisk
exten => s,n,Set(PAYLOAD=${DB(intercom/${EXTEN})})
exten => s,n,Set(CALLID=${CUT(PAYLOAD,|,2)})  ; 2nd field is call_id
```

**Option B: Pass as environment variable**
```bash
# In your script/dialplan invocation, pass the call_id
export CALLID=<the-django-call-id>
```

### Step 3: Test It

1. **Start your Django server:**
   ```bash
   python manage.py runserver 192.168.0.2:8000
   ```

2. **Make a test call:**
   ```bash
   curl -X POST http://192.168.0.2:8000/api/v1/voip/calls/ \
     -H "Content-Type: application/json" \
     -d '{"resident":"unit-test", "target":"+27656231093", "account_id":1}'
   ```
   Note the `call_id` in response.

3. **Check database immediately:**
   ```bash
   curl http://192.168.0.2:8000/api/v1/voip/calls/<call-id>/
   ```
   Should see: `"provider_call_id": "2d7b06d7-67ac-4e24-9562-e1d3520f5fb2"`

4. **Simulate webhook event:**
   ```bash
   curl -X POST http://192.168.0.2:8000/api/v1/voip/ami-event/ \
     -d "call_id=2d7b06d7-67ac-4e24-9562-e1d3520f5fb2&event=ringing&dial_status="
   ```

5. **Check status updated:**
   ```bash
   curl http://192.168.0.2:8000/api/v1/voip/calls/<call-id>/
   ```
   Should show: `"call_status": "ringing"`

## How It Works

```
Asterisk                      Django Backend              Android App
  |                                 |                          |
  |-- originate call with TOKEN    |                          |
  |    (stores call_id in AstDB)    |                          |
  |                                 |                          |
  |                          (call created)                    |
  |                     provider_call_id = call_id             |
  |                          (returned)                        |
  |                                 |← POST /api/v1/voip/calls/|
  |                                 |                    (call created)
  |                                 |← GET /api/v1/voip/calls/ |
  |  (dialplan retrieves call_id)   |                (empty status)
  |  (call starts ringing)          |                          |
  |-- POST /ami-event/ ----------→  |                          |
  |    call_id=...                  | provider_call_id found!  |
  |    event=ringing                | call_status = "ringing"  |
  |    dial_status=""               |                          |
  |                                 |← GET /api/v1/voip/calls/ |
  |                                 |           (now has status)|
  |  (call is answered)             |                          |
  |-- POST /ami-event/ ----------→  |                          |
  |    call_id=...                  | call_status = "answered" |
  |    event=hangup                 |                          |
  |    dial_status=ANSWER           |                          |
  |                                 |← GET /api/v1/voip/calls/ |
  |                                 |         (call completed) |
```

## Webhook Endpoints

**Supports two parameter styles:**

### For Script Method:
```bash
POST /api/v1/voip/ami-event/
- call_id=<django-call-uuid>
- event=ringing|answered|hangup
- dial_status=ANSWER|NOANSWER|BUSY|CANCEL|CONGESTION
```

### For AMI Method (with ASTERISK_HOST configured):
```bash
POST /api/v1/voip/ami-event/
- action_id=<asterisk-action-uuid>
- event=ringing|answered|hangup
- dial_status=ANSWER|NOANSWER|...
```

## Expected Status Values

After webhook is received:

| Event | Status |
|-------|--------|
| ringing | "ringing" |
| answered | "answered" |
| hangup + ANSWER | "answered" |
| hangup + NOANSWER | "no-answer" |
| hangup + BUSY | "busy" |
| hangup + CANCEL | "canceled" |
| hangup + CONGESTION | "failed" |

## Database Check

```bash
# Login to Django shell
python manage.py shell

# Check last 5 calls
from voip.models import VoipCall
for call in VoipCall.objects.order_by('-created_at')[:5]:
    print(f"{call.id}: provider_call_id={call.provider_call_id} status={call.call_status}")
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `provider_call_id` still empty after call | Is `voip_originate_call.sh` running? Check logs: "Set provider_call_id for script-based call" |
| `call_status` not updating | Is Asterisk dialplan sending webhook events? Check: `curl ... /ami-event/` returns 200 |
| Webhook returns 404 | Is `call_id` parameter correct? Must match exactly what Django stored |
| Webhook returns 400 | Missing both `call_id` AND `action_id` parameters |

## Android App Changes Needed

Update Android polling to show real status:

```kotlin
// Instead of checking if status == "" (empty)
if (callStatus.isEmpty()) {
    // Old: keep polling forever
} else {
    // New: show actual status
    showStatus(callStatus)  // "ringing", "answered", "no-answer", etc.
}
```

## Files Modified

- `backend/voip/tasks.py` — Sets provider_call_id when using script
- `backend/voip/views.py` — Webhook accepts both call_id and action_id
- `backend/voip/tests/test_voip.py` — 8 tests verify webhook works
- `backend/ASTERISK_AMI_SETUP.md` — Complete setup guide

## What Happens Now

✅ Call initiated → `provider_call_id` = Django call_id (auto-set)  
✅ Webhook sent → Django finds call and updates `call_status`  
✅ Android polls → Gets real status (ringing → answered → completed)  
✅ User experience → Instant feedback on call state

---

**Questions?** Check [ASTERISK_AMI_SETUP.md](ASTERISK_AMI_SETUP.md) for detailed examples and troubleshooting.
