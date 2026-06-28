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
            identifier='admin@example.com',
            name='Admin User',
            password='password123',
            is_staff=True
        )
        
        # Create a regular user
        self.regular_user = User.objects.create_user(
            identifier='regular@example.com',
            name='Regular User',
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
            name="Jane Transfer",
            amount=50000.00,
            method="Transfer",
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
            idempotency_key="8a7e0892-7473-455b-8664-9be7bd65f3f0"
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
        self.assertEqual(data['transfer'], 200000.00) # Bob (150k) + Jane (50k)
        self.assertEqual(data['pledges'], 200000.00)
        self.assertEqual(data['paystack'], 500000.00)
        
        # target is 5,000,000. 1,000,000 raised = 20%
        self.assertEqual(data['progress_percentage'], 20)
        
        # Test filters: status=approved
        response = self.client.get(url, {'status': 'approved'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3) # Transfer(Jane, Bob), Pledge
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

    def test_custom_inflow_category_filtering(self):
        from contributions.models import InflowCategory
        category1 = InflowCategory.objects.create(name="Youth Pledge Drive")
        category2 = InflowCategory.objects.create(name="Harvest Program Extra")

        # Assign categories
        self.c2.inflow_category = category1
        self.c2.save()
        self.c3.inflow_category = category2
        self.c3.save()

        self.client.force_authenticate(user=self.admin_user)
        url = reverse('dashboard:admin_transaction_list')

        # Filter by category 1
        response = self.client.get(url, {'category_id': category1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return self.c2 (Jane Transfer)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], "Jane Transfer")

    def test_role_based_permissions(self):
        # Create usher, approver, member
        usher_user = User.objects.create_user(identifier='usher@example.com', name='Usher User', password='password123', role='usher')
        approver_user = User.objects.create_user(identifier='approver@example.com', name='Approver User', password='password123', role='approver')
        member_user = User.objects.create_user(identifier='member@example.com', name='Member User', password='password123', role='member')

        # Helper assertions
        self.assertTrue(usher_user.is_usher)
        self.assertFalse(usher_user.is_approver)
        self.assertTrue(approver_user.is_approver)
        self.assertFalse(approver_user.is_usher)
        self.assertFalse(member_user.is_usher)
        self.assertFalse(member_user.is_approver)

        # Test view access using standard Django Client (Session auth)
        self.client.force_login(member_user)
        
        # Member tries to access live entry -> redirect
        response = self.client.get(reverse('dashboard:live_entry'))
        self.assertEqual(response.status_code, 302)

        # Member tries to access approval center -> redirect
        response = self.client.get(reverse('dashboard:approval_center'))
        self.assertEqual(response.status_code, 302)

        # Usher accesses live entry -> OK
        self.client.force_login(usher_user)
        response = self.client.get(reverse('dashboard:live_entry'))
        self.assertEqual(response.status_code, 200)

        # Approver accesses approval center -> OK
        self.client.force_login(approver_user)
        response = self.client.get(reverse('dashboard:approval_center'))
        self.assertEqual(response.status_code, 200)

    def test_pin_reset_flow(self):
        from accounts.models import PinResetRequest
        member_user = User.objects.create_user(identifier='08012345678', name='Phone Member', password='password123', role='member')
        
        # Request reset via POST
        self.client.force_login(member_user)
        response = self.client.post(reverse('accounts:forgot_pin'), {'identifier': '08012345678'})
        self.assertEqual(response.status_code, 302) # redirects to login

        # Check request created
        req = PinResetRequest.objects.get(member=member_user)
        self.assertFalse(req.is_resolved)
        self.assertIn("2348012345678", req.whatsapp_link)

        # Admin approves reset
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('dashboard:approve_pin_reset', args=[req.id]))
        self.assertEqual(response.status_code, 302)

        req.refresh_from_db()
        self.assertTrue(req.is_resolved)
        self.assertIsNotNone(req.temp_pin)
        self.assertEqual(len(req.temp_pin), 4)

    def test_flyer_locking_and_admin_update(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Log in regular user
        self.client.force_login(self.regular_user)
        
        # Verify flyer not locked by default
        self.assertFalse(self.regular_user.is_flyer_locked)
        
        # Admin updates flyer and locks it
        self.client.force_login(self.admin_user)
        
        # Prepare mock files
        profile_pic = SimpleUploadedFile("new_pic.jpg", b"file_content", content_type="image/jpeg")
        custom_flyer = SimpleUploadedFile("new_flyer.jpg", b"flyer_content", content_type="image/jpeg")
        
        # Post to admin flyer update endpoint
        url = reverse('dashboard:admin_update_member_flyer', args=[self.regular_user.id])
        response = self.client.post(url, {
            'profile_picture': profile_pic,
            'custom_flyer': custom_flyer,
            'is_flyer_locked': 'on'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify changes in DB
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_flyer_locked)
        self.assertTrue(self.regular_user.profile_picture.name.startswith('profiles/new_pic'))
        self.assertTrue(self.regular_user.custom_flyer.name.startswith('flyers/new_flyer'))
        
        # Now regular user logs back in and tries to update settings with a new picture
        self.client.force_login(self.regular_user)
        another_pic = SimpleUploadedFile("another_pic.jpg", b"another_content", content_type="image/jpeg")
        
        settings_url = reverse('accounts:settings')
        response = self.client.post(settings_url, {
            'profile_picture': another_pic
        })
        self.assertEqual(response.status_code, 302)
        
        # Check that profile picture was NOT changed
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.profile_picture.name.startswith('profiles/new_pic'))
        self.assertFalse(self.regular_user.profile_picture.name.startswith('profiles/another_pic'))

