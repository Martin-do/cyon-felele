from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
import requests
from django.utils import timezone
from datetime import timedelta
from contributions.models import Contribution

User = get_user_model()

class AdminDashboardAPITests(APITestCase):
    def setUp(self):
        # Create an admin user
        self.admin_user = User.objects.create_user(
            username='admin_user',
            name='Admin User',
            email='admin@example.com',
            password='password123',
            is_staff=True
        )
        
        # Create a regular user
        self.regular_user = User.objects.create_user(
            username='regular_user',
            name='Regular User',
            email='regular@example.com',
            password='password123',
            is_staff=False
        )

        # Create contributions
        self.c1 = Contribution.objects.create(
            name="John Cash",
            amount=100000.00,
            method="Cash",
            status="pending"
        )
        self.c2 = Contribution.objects.create(
            name="Jane POS",
            amount=50000.00,
            method="POS",
            status="approved"
        )
        self.c3 = Contribution.objects.create(
            name="Bob Transfer",
            amount=150000.00,
            method="Transfer",
            status="approved"
        )
        self.c4 = Contribution.objects.create(
            name="Alice Pledge",
            amount=200000.00,
            method="Pledge payment",
            status="approved"
        )
        self.c5 = Contribution.objects.create(
            name="Charlie Paystack",
            amount=500000.00,
            method="Paystack",
            status="pending",
            idempotency_key="paystack-ref-123"
        )
        self.c_voided = Contribution.objects.create(
            name="Voided User",
            amount=900000.00,
            method="Cash",
            status="approved",
            is_voided=True
        )

    def test_list_transactions_requires_auth_and_staff(self):
        url = reverse('dashboard:admin_transaction_list')
        
        # Anonymous
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Non-staff
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Staff
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_transactions_filters_and_stats(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:admin_transaction_list')
        
        # Without filters, check stats
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Statistics should be in root level
        data = response.data
        self.assertIn('total_raised', data)
        self.assertIn('cash', data)
        self.assertIn('pos', data)
        self.assertIn('transfer', data)
        self.assertIn('pledges', data)
        self.assertIn('paystack', data)
        self.assertIn('progress_percentage', data)
        self.assertIn('results', data)
        
        # Expected counts (excluding voided)
        self.assertEqual(data['count'], 5)
        # Expected total sum = 100k + 50k + 150k + 200k + 500k = 1,000,000
        self.assertEqual(data['total_raised'], 1000000.00)
        self.assertEqual(data['cash'], 100000.00)
        self.assertEqual(data['pos'], 50000.00)
        self.assertEqual(data['transfer'], 150000.00)
        self.assertEqual(data['pledges'], 200000.00)
        self.assertEqual(data['paystack'], 500000.00)
        
        # target is 5,000,000. 1,000,000 raised = 20%
        self.assertEqual(data['progress_percentage'], 20)
        
        # Test filters: status=approved
        response = self.client.get(url, {'status': 'approved'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3) # POS, Transfer, Pledge
        self.assertEqual(response.data['total_raised'], 400000.00)

        # Test filters: method=Cash (case-insensitive)
        response = self.client.get(url, {'method': 'cash'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], "John Cash")

    def test_contribution_action_approve_and_reject(self):
        self.client.force_authenticate(user=self.admin_user)
        
        # Approve action
        url = reverse('dashboard:contribution_action', args=[self.c1.id])
        response = self.client.post(url, {'action': 'approve', 'reason': 'Verified proof'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['contribution_status'], 'approved')
        
        # Check DB
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'approved')
        
        # Reject action
        url = reverse('dashboard:contribution_action', args=[self.c5.id])
        response = self.client.post(url, {'action': 'reject', 'reason': 'Fake receipt'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['contribution_status'], 'rejected')
        
        # Check DB
        self.c5.refresh_from_db()
        self.assertEqual(self.c5.status, 'rejected')

    @patch('requests.get')
    def test_requery_paystack_success(self, mock_get):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:requery_paystack', args=[self.c5.id])
        
        # Mock successful Paystack response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': True,
            'data': {
                'status': 'success',
                'amount': 50000000, # in kobo
            }
        }
        mock_get.return_value = mock_response
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['contribution_status'], 'approved')
        
        self.c5.refresh_from_db()
        self.assertEqual(self.c5.status, 'approved')

    @patch('requests.get')
    def test_requery_paystack_failed(self, mock_get):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:requery_paystack', args=[self.c5.id])
        
        # Mock failed Paystack response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': True,
            'data': {
                'status': 'failed',
            }
        }
        mock_get.return_value = mock_response
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['contribution_status'], 'rejected')
        
        self.c5.refresh_from_db()
        self.assertEqual(self.c5.status, 'rejected')

    def test_requery_paystack_validation(self):
        self.client.force_authenticate(user=self.admin_user)
        
        # Non-Paystack contribution
        url = reverse('dashboard:requery_paystack', args=[self.c1.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Transaction method is not', response.data['error'])
        
        # Paystack contribution with no idempotency key
        c_no_key = Contribution.objects.create(
            name="No Key Paystack",
            amount=50000.00,
            method="Paystack",
            status="pending"
        )
        url = reverse('dashboard:requery_paystack', args=[c_no_key.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Transaction does not have an idempotency key', response.data['error'])
