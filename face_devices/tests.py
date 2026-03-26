from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from GateCore.api_views.device_sync import queue_face_device_person_sync
from GateCore.models import GateTerminal, Person
from face_devices.models import FaceDeviceAction, FaceDeviceStrangerEvent
from face_devices.services import dequeue_pending_actions, ingest_face_device_access_log, queue_face_device_action


class FaceDeviceActionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="face_device_user", password="face-device-pass")
        self.staff_user = user_model.objects.create_user(username="face_device_staff", password="face-device-pass", is_staff=True)
        self.terminal = GateTerminal.objects.create(
            serial_number="TMT-CTRL-001",
            display_name="TMT Controller 1",
            approval_status="approved",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff_user)

    def test_edit_user_action_builds_edit_user_command(self):
        queue_face_device_action(
            terminal=self.terminal,
            action="edit_user",
            request_payload={
                "user_id": "visitor-1",
                "name": "Visitor Updated",
                "tts_name": "Visitor Updated",
            },
            requested_by=self.user,
        )

        commands = dequeue_pending_actions(
            terminal=self.terminal,
            device_identifier=self.terminal.serial_number,
            remote_ip="10.0.0.10",
            device_type="device",
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["cmd"], "editUser")
        self.assertEqual(commands[0]["user_id"], "visitor-1")

    def test_stranger_upload_is_logged_as_unknown(self):
        rows = ingest_face_device_access_log(
            terminal=self.terminal,
            device_identifier=self.terminal.serial_number,
            command="uploadStrangerRecord",
            payload={
                "device_id": self.terminal.serial_number,
                "timestamp": "2026-03-24 09:16:00",
                "face_image": "data:image/jpeg;base64,ZmFrZQ==",
                "liveness_score": 45.2,
                "code": 0,
                "status": "stranger",
            },
            remote_ip="10.0.0.10",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].result, "unknown")
        self.assertIsNone(rows[0].person)

    def test_person_sync_uses_terminal_face_group_config(self):
        self.terminal.config = {"default_face_group": "residents-main"}
        self.terminal.save(update_fields=["config", "modified_at"])
        person = Person.objects.create(
            first_name="Face",
            last_name="Resident",
            phone="+27123456789",
            facial_recognition_enabled=True,
            face_enrollment_status="approved",
            photo=SimpleUploadedFile("face.jpg", b"fake-image-bytes", content_type="image/jpeg"),
        )

        queued = queue_face_device_person_sync(person, requested_by=self.user)

        self.assertEqual(queued, 1)
        action = FaceDeviceAction.objects.get(device_identifier=self.terminal.serial_number, action="add_user")
        self.assertEqual(action.request_payload.get("face_group_name"), "residents-main")

    def test_create_group_action_builds_create_group_command(self):
        queue_face_device_action(
            terminal=self.terminal,
            action="create_group",
            request_payload={"group_name": "visitors"},
            requested_by=self.user,
        )

        commands = dequeue_pending_actions(
            terminal=self.terminal,
            device_identifier=self.terminal.serial_number,
            remote_ip="10.0.0.10",
            device_type="device",
        )

        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["cmd"], "createGroup")
        self.assertEqual(commands[0]["group_name"], "visitors")

    def test_stranger_review_endpoint_updates_status(self):
        rows = ingest_face_device_access_log(
            terminal=self.terminal,
            device_identifier=self.terminal.serial_number,
            command="uploadStrangerRecord",
            payload={
                "device_id": self.terminal.serial_number,
                "timestamp": "2026-03-24 09:16:00",
                "face_image": "data:image/jpeg;base64,ZmFrZQ==",
                "status": "stranger",
            },
            remote_ip="10.0.0.10",
        )
        self.assertEqual(len(rows), 1)
        stranger = FaceDeviceStrangerEvent.objects.get(access_log=rows[0])

        response = self.client.patch(
            f"/api/v1/face-devices/strangers/{stranger.id}/",
            {"status": "reviewed", "review_notes": "Guard checked visitor"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        stranger.refresh_from_db()
        self.assertEqual(stranger.status, "reviewed")
        self.assertEqual(stranger.review_notes, "Guard checked visitor")

    def test_access_logs_endpoint_handles_unresolved_event_user_name(self):
        ingest_face_device_access_log(
            terminal=self.terminal,
            device_identifier=self.terminal.serial_number,
            command="uploadStrangerRecord",
            payload={
                "user_id": "F1000001",
                "user_name": "Resident 27656231093",
                "recog_time": "2026-03-24 19:50:41",
                "confidence": "86.02906",
                "pass_status": 1,
                "photo": "data:image/jpeg;base64,ZmFrZQ==",
            },
            remote_ip="10.0.0.10",
        )

        response = self.client.get("/api/v1/face-devices/access-logs/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["items"][0]["event_user_name"], "Resident 27656231093")

    def test_access_logs_person_filter_matches_payload_fields(self):
        ingest_face_device_access_log(
            terminal=self.terminal,
            device_identifier=self.terminal.serial_number,
            command="uploadStrangerRecord",
            payload={
                "user_id": "F1000001",
                "user_name": "Resident 27656231093",
                "recog_time": "2026-03-24 19:50:41",
                "confidence": "86.02906",
                "pass_status": 1,
                "photo": "data:image/jpeg;base64,ZmFrZQ==",
            },
            remote_ip="10.0.0.10",
        )

        response = self.client.get("/api/v1/face-devices/access-logs/", {"person": "27656231093"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["items"][0]["event_user_id"], "F1000001")
