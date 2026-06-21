from django.test import TestCase
from django.urls import reverse

class LandingPageTest(TestCase):
    def test_landing_page_renders(self):
        url = reverse('contributions:landing')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_landing_page_contains_mobile_responsive_css(self):
        url = reverse('contributions:landing')
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        
        # Verify will-change property is present on .reveal
        self.assertIn('will-change: transform, opacity;', content)
        # Verify the new responsive styles are present
        self.assertIn('.hero-topbar img.cyon-logo', content)
        self.assertIn('.account-number {', content)
        self.assertIn('/* R1. Topbar & Logos */', content)

    def test_custom_404_renders_correctly(self):
        # Request a non-existent URL
        response = self.client.get('/this-url-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        content = response.content.decode('utf-8')
        # Verify our custom template elements are present
        self.assertIn('Page Not Found', content)
        self.assertIn('Sowing in the wrong soil?', content)
        self.assertIn('Return to Harvest Landing Page', content)
    def test_copy_acct_function_receives_event(self):
        url = reverse('contributions:landing')
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        # Verify the button markup passes 'event' to copyAcct
        self.assertIn('onclick="copyAcct(event)"', content)
        # Verify the script function definition accepts the 'event' argument
        self.assertIn('function copyAcct(event)', content)

from contributions.models import Contribution

class LogoLinksTest(TestCase):
    def test_landing_page_logo_links(self):
        url = reverse('contributions:landing')
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        landing_url = reverse('contributions:landing')
        
        # Verify Archdiocese seal link
        self.assertIn(f'<a href="{landing_url}" class="logo-link">', content)
        self.assertIn('src="/static/images/brand/church-seal.png"', content)
        self.assertIn('src="/static/images/brand/cyon-logo.png"', content)

    def test_donation_form_logo_links(self):
        url = reverse('contributions:generic_donation')
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        landing_url = reverse('contributions:landing')
        
        # In base.html site header
        self.assertIn(f'<a href="{landing_url}" class="logo-link">', content)
        self.assertIn('src="/static/images/brand/church-seal.png"', content)
        self.assertIn('src="/static/images/brand/cyon-logo.png"', content)

    def test_receipt_logo_links(self):
        contribution = Contribution.objects.create(
            name="Test Contributor",
            amount=5000.00,
            method="Cash",
            phone="08012345678"
        )
        url = reverse('contributions:receipt', args=[contribution.id])
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        landing_url = reverse('contributions:landing')
        
        # Check base.html site header
        self.assertIn(f'<a href="{landing_url}" class="logo-link">', content)
        self.assertIn('src="/static/images/brand/church-seal.png"', content)
        self.assertIn('src="/static/images/brand/cyon-logo.png"', content)

