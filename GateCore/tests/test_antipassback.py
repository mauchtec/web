from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from GateCore.models import AccessLog


class AntiPassbackTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="apb_user", password="apb_pass_123")
        self.client.force_authenticate(user=self.user)
        self.url = "/api/gatecore/access-logs/"

    def _payload(self, direction, credential_value="CARD-001", **extra):
        request_data = {
            "direction": direction,
            "anti_passback_enabled": True,
        }
        request_data.update(extra.pop("request_data", {}))
        payload = {
            "result": "granted",
            "credential_value_used": credential_value,
            "request_data": request_data,
        }
        payload.update(extra)
        return payload

    def test_exit_without_recent_entry_is_denied(self):
        response = self.client.post(self.url, self._payload("exit"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "ANTI_PASSBACK")

    def test_manual_override_requires_comment(self):
        payload = self._payload(
            "exit",
            anti_passback_override=True,
        )
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "ANTI_PASSBACK_OVERRIDE_COMMENT_REQUIRED")

    def test_manual_override_allows_exit_and_audits_comment(self):
        payload = self._payload(
            "exit",
            anti_passback_override=True,
            anti_passback_override_comment="Company car change",
        )
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = AccessLog.objects.get(id=response.data["id"])
        self.assertEqual(log.request_data.get("anti_passback_status"), "OVERRIDE_ALLOWED")
        self.assertEqual(log.request_data.get("anti_passback_override_comment"), "Company car change")

    def test_reentry_without_exit_is_denied_by_default(self):
        first_entry = self.client.post(self.url, self._payload("entry"), format="json")
        self.assertEqual(first_entry.status_code, status.HTTP_201_CREATED)

        second_entry = self.client.post(self.url, self._payload("entry"), format="json")
        self.assertEqual(second_entry.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_entry.data.get("code"), "ANTI_PASSBACK_ALREADY_INSIDE")

    def test_exit_closes_all_open_entries_for_same_identity(self):
        relaxed_guard = {"enforce_no_reentry_without_exit": False}
        first_entry = self.client.post(
            self.url,
            self._payload("entry", request_data=relaxed_guard),
            format="json",
        )
        second_entry = self.client.post(
            self.url,
            self._payload("entry", request_data=relaxed_guard),
            format="json",
        )
        self.assertEqual(first_entry.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_entry.status_code, status.HTTP_201_CREATED)

        exit_response = self.client.post(
            self.url,
            self._payload("exit", request_data=relaxed_guard),
            format="json",
        )
        self.assertEqual(exit_response.status_code, status.HTTP_201_CREATED)
        exit_log = AccessLog.objects.get(id=exit_response.data["id"])

        entry_one = AccessLog.objects.get(id=first_entry.data["id"])
        entry_two = AccessLog.objects.get(id=second_entry.data["id"])
        self.assertEqual(entry_one.request_data.get("anti_passback_status"), "CLOSED_BY_EXIT")
        self.assertEqual(entry_two.request_data.get("anti_passback_status"), "CLOSED_BY_EXIT")
        self.assertEqual(entry_one.request_data.get("anti_passback_closed_by_exit_id"), str(exit_log.id))
        self.assertEqual(entry_two.request_data.get("anti_passback_closed_by_exit_id"), str(exit_log.id))

        closed_ids = exit_log.request_data.get("anti_passback_closed_entry_ids") or []
        self.assertEqual(set(closed_ids), {str(entry_one.id), str(entry_two.id)})

    def test_exit_with_direction_at_top_level_is_validated(self):
        """Exit with direction at payload root (not inside request_data) is still validated and blocked when no entry."""
        payload = {
            "result": "granted",
            "direction": "exit",
            "credential_value_used": "NO-PRIOR-ENTRY",
            "anti_passback_enabled": True,
            "request_data": {},
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "ANTI_PASSBACK")

    def test_exit_with_direction_and_plate_in_components_is_validated(self):
        """Exit with direction and number_plate inside components (app payload shape) is validated and blocked when no entry."""
        payload = {
            "result": "granted",
            "anti_passback_enabled": True,
            "request_data": {
                "workflow_id": "exit-workflow-1",
                "workflow_name": "Vehicle Exit",
                "components": [
                    {"id": "dir1", "type": "direction_field", "direction": "exit"},
                    {"id": "vehicle1", "type": "vehicle_disk", "number_plate": "NZK612GP"},
                ],
            },
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "ANTI_PASSBACK")

    def test_exit_with_vehicle_card_fields_shape_is_validated(self):
        """Exit with direction_card + vehicle_card (fields with Plate label) is validated and blocked when no entry."""
        payload = {
            "result": "granted",
            "anti_passback_enabled": True,
            "request_data": {
                "workflow_id": "f854ec80-8dbc-428b-b228-530d00115b22",
                "workflow_name": "Exit",
                "components": [
                    {"id": "direction_card_n5ko68", "type": "direction_card", "direction": "exit"},
                    {"id": "vehicle_card_0v77do", "type": "vehicle_card", "fields": [
                        {"label": "Plate", "value": "NZK612GP"},
                        {"label": "Make/Model", "value": "Toyota"},
                        {"label": "Color", "value": "White"},
                    ]},
                ],
            },
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "ANTI_PASSBACK")
