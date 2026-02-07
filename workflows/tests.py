from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Workflow, WorkflowSubmission
import json

class WorkflowSubmissionTestCase(APITestCase):
    """Test cases for workflow submission functionality"""
    
    def setUp(self):
        """Create a test workflow"""
        self.workflow = Workflow.objects.create(
            name="TestWorkflow",
            description="Test workflow for submissions",
            version="1.0.0",
            status="published",
            definition={
                "steps": [
                    {
                        "id": "name_card_1",
                        "type": "name_card",
                        "props": {
                            "card_label": "Full Name",
                            "placeholder": "Enter your name"
                        }
                    },
                    {
                        "id": "phone_card_1",
                        "type": "phone_card",
                        "props": {
                            "card_label": "Phone Number",
                            "placeholder": "Enter phone"
                        }
                    }
                ]
            }
        )
    
    def test_submit_workflow_data_success(self):
        """Test successful workflow data submission"""
        url = reverse('submit_workflow_data', args=[self.workflow.id])
        data = {
            "data": {
                "name_card_1": "John Doe",
                "phone_card_1": "+1234567890"
            },
            "submitted_by": "test_user",
            "session_id": "test_session_123"
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['workflow_id'], str(self.workflow.id))
        self.assertIn('message', response.data)
        
        # Verify submission was created in database
        submission = WorkflowSubmission.objects.get(id=response.data['id'])
        self.assertEqual(submission.workflow, self.workflow)
        self.assertEqual(submission.submission_data['name_card_1'], "John Doe")
        self.assertEqual(submission.submitted_by, "test_user")
    
    def test_submit_workflow_data_missing_data(self):
        """Test workflow submission with missing data"""
        url = reverse('submit_workflow_data', args=[self.workflow.id])
        data = {}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_submit_workflow_data_invalid_workflow(self):
        """Test workflow submission with invalid workflow ID"""
        import uuid
        invalid_id = uuid.uuid4()
        url = reverse('submit_workflow_data', args=[invalid_id])
        data = {
            "data": {"test": "value"}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_list_workflow_submissions(self):
        """Test listing workflow submissions"""
        # Create some test submissions
        for i in range(3):
            WorkflowSubmission.objects.create(
                workflow=self.workflow,
                submission_data={"field": f"value_{i}"},
                submitted_by=f"user_{i}"
            )
        
        url = reverse('list_workflow_submissions', args=[self.workflow.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 3)
        self.assertEqual(len(response.data['results']), 3)
        self.assertEqual(response.data['workflow_name'], "TestWorkflow")
    
    def test_list_workflow_submissions_pagination(self):
        """Test pagination of workflow submissions"""
        # Create 5 submissions
        for i in range(5):
            WorkflowSubmission.objects.create(
                workflow=self.workflow,
                submission_data={"field": f"value_{i}"}
            )
        
        url = reverse('list_workflow_submissions', args=[self.workflow.id])
        response = self.client.get(url, {'per_page': 2, 'page': 1})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 5)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['per_page'], 2)
