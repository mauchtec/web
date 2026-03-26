# Permissions and tokens for +15551234567 (and “Security” group)

## What +15551234567 has today

The number **+15551234567** is stored as a **Person** in GateCore. When that person logs in via the Android app (OTP), the backend:

1. **Person**  
   - `Person.phone` = normalized +15551234567  
   - `Person.user` = linked Django auth User

2. **Django User**  
   - Created by `ensure_mobile_user()` in `GateCore/services/mobile_auth.py`  
   - User is added to the **Operator** group (Django auth group, not GateCore Group).

3. **Token**  
   - REST Framework auth token: `rest_framework.authtoken.models.Token`  
   - Created in `build_token_response()`: `Token.objects.get_or_create(user=user)`  
   - Returned to the app after OTP verify; the app sends `Authorization: Token <key>` on API requests.

4. **Why they see all workflows**  
   - Workflow API uses `WorkflowRolePermission` in `accounts/permissions.py`.  
   - **Read (GET)** is allowed if the user is in one of:  
     `Operator`, `SecurityManager`, `Admin`, `Auditor`, `Device`.  
   - +15551234567’s user is in **Operator**, so they get **read** access to all workflows.  
   - **Write** is allowed for: `SecurityManager`, `Admin`, `Device`, and also `Operator`, `Auditor`.

So the permissions and “token” that make workflows visible are:

- **Token:** `Authorization: Token <key>` (the key from `Token.objects.get_or_create(user=user)`).
- **Permissions:** User in Django group **Operator** (and optionally **SecurityManager**, **Admin**, etc. for more access).

## Making “numbers in that unit” have the same (Security group)

To give the same workflow (and future) access to **all numbers in a unit**, we tie it to **GateCore Groups**:

- A **GateCore Group** (e.g. “Security”) can be marked **“grants workflow access”**.
- **Units** are assigned to that group (UnitGroupMembership).
- When a **person** logs in via mobile (OTP), we check if they have an **active occupancy** in a **unit** that belongs to a group with **“grants workflow access”**.
- If yes, we add the same Django groups (e.g. **Operator**) to their User so they get the same workflow (and token) behavior as +15551234567.

So:

- **Permissions/tokens** that +15551234567 uses = **Operator** (Django group) + **Token** auth.
- **“Assigned to the group security”** = **GateCore Group** (e.g. “Security”) with **grants_workflow_access = True**, and the **units** that should have that access are **members of that group**. Anyone in those units then gets **Operator** (and same token behavior) on mobile login.

## What was implemented

- **GateCore Group** has a flag **`grants_workflow_access`**. When True, any person who has an active occupancy in a **unit in that group** gets the **Operator** Django group (and thus workflow access) on mobile login.
- **Security group**: A **Security** group was created with `grants_workflow_access=True`, and the unit where +15551234567 has occupancy was added to it. So +15551234567 and any other number in that unit get the same permissions and token behavior.
- **Backward compatibility**: If no GateCore group has `grants_workflow_access=True`, every mobile user still gets Operator (unchanged). As soon as at least one group has the flag, only people in units in those groups get Operator.

To add more units to Security (so their numbers get workflow access):

```bash
python manage.py setup_security_group_workflow_access --units A-101,B-201
```

Or create another group in admin, set **grants_workflow_access** = True, and add units to it.

## Summary

| What              | Where / How |
|-------------------|-------------|
| Phone             | Person.phone = +15551234567 |
| Django User       | Person.user (created by ensure_mobile_user) |
| Token             | `Token` for that user; sent as `Authorization: Token <key>` |
| Workflow access   | User in Django group **Operator** (only if person’s unit is in a Group with **grants_workflow_access** = True) |
| “Group security”  | GateCore **Group** “Security” with **grants_workflow_access = True**; the unit where +15551234567 lives is in this group; all numbers in that unit get Operator + token on login |
