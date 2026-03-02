import uuid
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import VoipCall
from .tasks import initiate_sip_call
from .views import _map_asterisk_status


class VoipCallModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_voip_call(self):
        call = VoipCall.objects.create(
            account=self.user,
            destination='+27656231093',
        )
        self.assertIsNotNone(call.id)
        self.assertEqual(call.call_status, '')
        self.assertEqual(call.provider_call_id, '')

    def test_str(self):
        call = VoipCall.objects.create(account=self.user, destination='+123')
        self.assertIn('+123', str(call))


class MapAsteriskStatusTest(TestCase):
    def test_originate_response_answer(self):
        self.assertEqual(_map_asterisk_status('originateresponse', 'answer'), 'answered')

    def test_originate_response_busy(self):
        self.assertEqual(_map_asterisk_status('originateresponse', 'busy'), 'busy')

    def test_originate_response_noanswer(self):
        self.assertEqual(_map_asterisk_status('originateresponse', 'noanswer'), 'no-answer')

    def test_originate_response_cancel(self):
        self.assertEqual(_map_asterisk_status('originateresponse', 'cancel'), 'cancelled')

    def test_originate_response_congestion(self):
        self.assertEqual(_map_asterisk_status('originateresponse', 'congestion'), 'failed')

    def test_dial_event(self):
        self.assertEqual(_map_asterisk_status('dial', ''), 'ringing')

    def test_hangup_answered(self):
        self.assertEqual(_map_asterisk_status('hangup', 'answer'), 'completed')

    def test_hangup_busy(self):
        self.assertEqual(_map_asterisk_status('hangup', 'busy'), 'busy')

    def test_unknown_event(self):
        self.assertEqual(_map_asterisk_status('unknown', ''), '')


class InitiateSipCallTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='caller', password='pass')
        self.call = VoipCall.objects.create(
            account=self.user,
            destination='+27656231093',
        )

    @patch('voip.tasks._ami_send_originate')
    def test_call_initiated_on_ami_success(self, mock_ami):
        mock_ami.return_value = ['Response: Success', 'ActionID: test-action-id']
        initiate_sip_call(str(self.call.id), '+27656231093', self.user.pk, '+27656231093')
        self.call.refresh_from_db()
        self.assertEqual(self.call.call_status, 'initiated')
        self.assertNotEqual(self.call.provider_call_id, '')
        self.assertIsNotNone(self.call.started_at)

    @patch('voip.tasks._ami_send_originate')
    def test_call_failed_on_ami_error(self, mock_ami):
        mock_ami.side_effect = RuntimeError("Connection refused")
        initiate_sip_call(str(self.call.id), '+27656231093', self.user.pk, '+27656231093')
        self.call.refresh_from_db()
        self.assertEqual(self.call.call_status, 'failed')
        self.assertIsNotNone(self.call.ended_at)

    def test_nonexistent_call_id(self):
        # Should not raise, just log
        initiate_sip_call(str(uuid.uuid4()), '+27656231093', self.user.pk)


class VoipCallAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='pass')
        self.client.force_authenticate(user=self.user)

    @patch('voip.views.threading.Thread')
    def test_create_call(self, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread
        resp = self.client.post('/api/v1/voip/calls/', {
            'destination': '+27656231093',
            'resident_id': str(uuid.uuid4()),
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn('id', data)
        self.assertIn('call_status', data)
        mock_thread.start.assert_called_once()

    def test_retrieve_call(self):
        call = VoipCall.objects.create(account=self.user, destination='+123')
        resp = self.client.get(f'/api/v1/voip/calls/{call.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], str(call.id))

    def test_list_calls(self):
        VoipCall.objects.create(account=self.user, destination='+1')
        VoipCall.objects.create(account=self.user, destination='+2')
        resp = self.client.get('/api/v1/voip/calls/')
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_rejected(self):
        unauthenticated = APIClient()
        resp = unauthenticated.get('/api/v1/voip/calls/')
        self.assertIn(resp.status_code, [401, 403])


class AmiEventWebhookTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='webhookuser', password='pass')
        self.call = VoipCall.objects.create(
            account=self.user,
            destination='+27656231093',
            provider_call_id='test-action-id',
            call_status='initiated',
        )

    def test_ami_event_updates_status_answered(self):
        resp = self.client.post('/api/v1/voip/ami-event/', {
            'action_id': 'test-action-id',
            'event': 'originateresponse',
            'dial_status': 'answer',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.call.refresh_from_db()
        self.assertEqual(self.call.call_status, 'answered')

    def test_ami_event_updates_status_failed(self):
        resp = self.client.post('/api/v1/voip/ami-event/', {
            'action_id': 'test-action-id',
            'event': 'originateresponse',
            'dial_status': 'congestion',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.call.refresh_from_db()
        self.assertEqual(self.call.call_status, 'failed')
        self.assertIsNotNone(self.call.ended_at)

    def test_ami_event_unknown_action_id(self):
        resp = self.client.post('/api/v1/voip/ami-event/', {
            'action_id': 'nonexistent',
            'event': 'hangup',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_ami_event_missing_action_id(self):
        resp = self.client.post('/api/v1/voip/ami-event/', {
            'event': 'hangup',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ami_event_hangup_sets_ended_at(self):
        resp = self.client.post('/api/v1/voip/ami-event/', {
            'action_id': 'test-action-id',
            'event': 'hangup',
            'dial_status': 'answer',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.call.refresh_from_db()
        self.assertEqual(self.call.call_status, 'completed')
        self.assertIsNotNone(self.call.ended_at)
