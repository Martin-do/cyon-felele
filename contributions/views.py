from rest_framework import generics
from django.shortcuts import render, get_object_or_404
import uuid
from .models import Contribution
from accounts.models import Member
from .serializers import ContributionSerializer

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Sum, Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
import requests
from django.conf import settings

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

def landing_page_view(request):
    total = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0
    count = Contribution.objects.filter(is_voided=False).count()
    target = 5000000
    progress = min(int((float(total) / target) * 100), 100) if total else 0
    return render(request, 'contributions/landing.html', {
        'total_harvest': total,
        'contributor_count': count,
        'progress_percentage': progress,
        'target': target,
    })


class NameSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        if not query or len(query) < 2:
            return Response([])
            
        from .models import Parishioner
        parishioners = Parishioner.objects.filter(name__icontains=query).values_list('name', flat=True)[:5]
        contributions = Contribution.objects.filter(name__icontains=query).values_list('name', flat=True).distinct()[:5]
        
        results = list(set(list(parishioners) + list(contributions)))
        results.sort()
        
        return Response(results[:5])

def get_unique_link_category():
    """InflowCategory used to tag contributions that arrive via a member's
    unique referral/voting link (e.g. /support/<slug>/). Looked up by name
    so it works with whatever's already created in the admin - if it's
    renamed or missing, contributions still save fine, just uncategorized."""
    from .models import InflowCategory
    return InflowCategory.objects.filter(name__iexact='Youth Harvest Fundraiser').first()


def notify_admins_of_pending_contribution(contribution):
    from accounts.models import Member, WebPushSubscription
    from dashboard.views import send_web_push
    from django.db.models import Q
    
    admins_and_approvers = Member.objects.filter(
        Q(role__in=['admin', 'approver']) | Q(is_superuser=True) | Q(is_staff=True)
    )
    subscriptions = WebPushSubscription.objects.filter(user__in=admins_and_approvers)
    payload = {
        'title': 'New Pending Contribution',
        'body': f"{contribution.name} submitted a pending {contribution.method} of ₦{contribution.amount:,.2f}.",
        'url': '/dashboard/'
    }
    for sub in subscriptions:
        send_web_push(sub, payload)


class ContributionCreateAPIView(generics.CreateAPIView):
    queryset = Contribution.objects.all()
    serializer_class = ContributionSerializer
    
    def perform_create(self, serializer):
        contribution = serializer.save()

        # Auto-tag contributions that came in via a member's unique link.
        if contribution.referred_by_id and not contribution.inflow_category_id:
            category = get_unique_link_category()
            if category:
                contribution.inflow_category = category
                contribution.save(update_fields=['inflow_category'])
        
        # Notify admins when a pending manual contribution is logged
        if contribution.status == 'pending':
            try:
                notify_admins_of_pending_contribution(contribution)
            except Exception as e:
                print(f"Failed to notify admins of pending contribution: {e}")
        
        # Trigger WebSocket push for Live Board
        channel_layer = get_channel_layer()
        total = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0.00
        
        display_name = 'Anonymous' if contribution.is_anonymous else contribution.name
        
        data = {
            'id': str(contribution.id),
            'name': display_name,
            'amount': str(contribution.amount),
            'source': contribution.source,
            'timestamp': contribution.timestamp.isoformat(),
            'total_harvest': str(total)
        }
        
        async_to_sync(channel_layer.group_send)(
            'live_board',
            {
                'type': 'new_contribution',
                'data': data
            }
        )

def donation_form_view(request, referral_slug=None):
    referrer = None
    leaderboard_position = None
    total_amount = 0
    
    if referral_slug:
        referrer = get_object_or_404(Member, referral_slug=referral_slug)
        
        # Calculate referrer's own total raised regardless of contestant status, so the progress bar works
        referrer_total = (
            Member.objects
            .filter(id=referrer.id)
            .annotate(
                total_raised=Sum(
                    'referrals__amount',
                    filter=Q(referrals__is_voided=False, referrals__status='approved') & ~Q(referrals__method__icontains='Pledge')
                )
            )
            .first()
        )
        total_amount = referrer_total.total_raised or 0.00 if referrer_total else 0.00

        # Calculate leaderboard position
        # Get all members with the same contestant title
        top_3 = []
        if referrer.contestant_title and referrer.contestant_title != 'None':
            competitors = (
                Member.objects
                .filter(is_active=True, is_staff=False, contestant_title=referrer.contestant_title)
                .annotate(
                    total_raised=Sum(
                        'referrals__amount',
                        filter=Q(referrals__is_voided=False, referrals__status='approved') & ~Q(referrals__method__icontains='Pledge')
                    )
                )
                .order_by('-total_raised')
            )

            for index, comp in enumerate(competitors):
                comp_total = comp.total_raised or 0.00
                rank = index + 1

                if index < 3:
                    top_3.append({
                        'rank': rank,
                        'name': comp.name,
                        'total': comp_total,
                        'votes': int(comp_total // 500),
                        'picture_url': comp.profile_picture.url if comp.profile_picture else None,
                        'initial': comp.name[0].upper(),
                    })

                if comp.id == referrer.id:
                    leaderboard_position = rank
                    total_amount = comp_total

        # Set a target amount for progress bars
        target_amount = 5000000 
        progress_percentage = min(int((total_amount / target_amount) * 100), 100)

        # Dynamically point to the public flyer endpoint so it generates on-demand for crawlers
        from django.urls import reverse
        import os
        from django.conf import settings
        
        flyers_dir = os.path.join(settings.MEDIA_ROOT, 'flyers')
        cache_path = os.path.join(flyers_dir, f"{referrer.id}.png")
        template_path = os.path.join(settings.BASE_DIR, 'dashboard', 'templates', 'dashboard', 'flyer.html')
        v = "1"
        mtimes = []
        if os.path.exists(cache_path):
            try:
                mtimes.append(os.path.getmtime(cache_path))
            except Exception:
                pass
        if os.path.exists(template_path):
            try:
                mtimes.append(os.path.getmtime(template_path))
            except Exception:
                pass
        if mtimes:
            v = str(int(max(mtimes)))
                
        og_image_url = request.build_absolute_uri(
            reverse('dashboard:public_flyer_versioned', args=[referrer.referral_slug, v])
        )

        context = {
            'referrer': referrer,
            'idempotency_key': str(uuid.uuid4()),
            'leaderboard_position': leaderboard_position,
            'total_amount': total_amount,
            'top_3': top_3,
            'progress_percentage': progress_percentage,
            'target_amount': target_amount,
            'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
            'og_image_url': og_image_url,
        }
        return render(request, 'contributions/contestant_vote.html', context)
        
    context = {
        'referrer': None,
        'idempotency_key': str(uuid.uuid4())
    }
    return render(request, 'contributions/donation_form.html', context)

def receipt_view(request, pk):
    contribution = get_object_or_404(Contribution, pk=pk)
    return render(request, 'contributions/receipt.html', {'contribution': contribution})

def custom_404(request, exception=None):
    return render(request, '404.html', status=404)

class VerifyPaystackPaymentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        reference = request.data.get('reference')
        name = request.data.get('name')
        phone = request.data.get('phone')
        referred_by_id = request.data.get('referred_by')
        is_anonymous = request.data.get('is_anonymous') == 'true'

        if not reference:
            return Response({'error': 'Reference is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify transaction with Paystack API
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }
        
        try:
            response = requests.get(url, headers=headers)
            res_data = response.json()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if res_data.get('status') and res_data.get('data', {}).get('status') == 'success':
            try:
                data = res_data['data']
                amount = (data['amount'] - data.get('fees', 0)) / 100.0  # Convert back from kobo, deducting Paystack fees

                referrer = None
                if referred_by_id:
                    try:
                        referrer = Member.objects.get(id=referred_by_id)
                    except (Member.DoesNotExist, ValueError):
                        pass

                referral_category = get_unique_link_category() if referrer else None

                # Check if contribution already exists for this reference (using idempotency_key = reference)
                contribution, created = Contribution.objects.get_or_create(
                    idempotency_key=reference,
                    defaults={
                        'name': name or 'Anonymous Paystack User',
                        'phone': phone,
                        'amount': amount,
                        'method': 'Online',
                        'source': 'guest_form',
                        'referred_by': referrer,
                        'inflow_category': referral_category,
                        'is_anonymous': is_anonymous,
                        'status': 'approved'
                    }
                )

                if created:
                    # Trigger WebSocket push for Live Board
                    try:
                        channel_layer = get_channel_layer()
                        total = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0.00
                        
                        display_name = 'Anonymous' if contribution.is_anonymous else contribution.name
                        
                        ws_data = {
                            'id': str(contribution.id),
                            'name': display_name,
                            'amount': str(contribution.amount),
                            'source': contribution.source,
                            'timestamp': contribution.timestamp.isoformat(),
                            'total_harvest': str(total)
                        }
                        
                        if channel_layer:
                            async_to_sync(channel_layer.group_send)(
                                'live_board',
                                {
                                    'type': 'new_contribution',
                                    'data': ws_data
                                }
                            )
                    except Exception as ws_err:
                        # Don't fail the payment if websocket push fails
                        pass

                return Response({'id': str(contribution.id), 'status': 'success'})
            except Exception as e:
                import traceback
                return Response({'error': f"Internal Server Error: {str(e)}", 'traceback': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        else:
            return Response({'error': 'Payment verification failed at Paystack'}, status=status.HTTP_400_BAD_REQUEST)


import hmac
import hashlib
import json

@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')

        if not signature:
            return Response({'status': 'ignored', 'reason': 'Missing signature'}, status=400)

        # Verify signature
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        if computed_signature != signature:
            return Response({'status': 'ignored', 'reason': 'Invalid signature'}, status=400)

        try:
            event_data = json.loads(payload)
        except Exception as e:
            return Response({'status': 'ignored', 'reason': f'Invalid JSON: {str(e)}'}, status=400)

        event = event_data.get('event')

        if event == 'charge.success':
            data = event_data.get('data', {})
            reference = data.get('reference')
            amount_kobo = data.get('amount', 0)
            fees_kobo = data.get('fees', 0)
            amount = (amount_kobo - fees_kobo) / 100.0

            metadata = data.get('metadata', {})
            custom_fields = metadata.get('custom_fields', [])
            name = None
            phone = None
            
            for field in custom_fields:
                if field.get('variable_name') == 'contributor_name':
                    name = field.get('value')
                elif field.get('variable_name') == 'phone_number':
                    phone = field.get('value')

            if not name:
                name = metadata.get('name') or (data.get('customer', {}).get('first_name', '') + ' ' + data.get('customer', {}).get('last_name', '')).strip()
            if not phone:
                phone = metadata.get('phone') or data.get('customer', {}).get('phone')

            referred_by_id = metadata.get('referred_by')
            is_anonymous = metadata.get('is_anonymous') == 'true' or metadata.get('is_anonymous') is True

            referrer = None
            if referred_by_id:
                try:
                    referrer = Member.objects.get(id=referred_by_id)
                except (Member.DoesNotExist, ValueError):
                    pass

            referral_category = get_unique_link_category() if referrer else None

            # Get or create contribution
            contribution, created = Contribution.objects.get_or_create(
                idempotency_key=reference,
                defaults={
                    'name': name or 'Anonymous Paystack User',
                    'phone': phone,
                    'amount': amount,
                    'method': 'Online',
                    'source': 'guest_form',
                    'referred_by': referrer,
                    'inflow_category': referral_category,
                    'is_anonymous': is_anonymous,
                    'status': 'approved'
                }
            )

            # If it already existed but was pending, mark it approved
            if not created and contribution.status != 'approved':
                contribution.status = 'approved'
                contribution.save(update_fields=['status'])

            if created:
                # Trigger WebSocket push for Live Board
                try:
                    channel_layer = get_channel_layer()
                    total = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0.00
                    display_name = 'Anonymous' if contribution.is_anonymous else contribution.name
                    ws_data = {
                        'id': str(contribution.id),
                        'name': display_name,
                        'amount': str(contribution.amount),
                        'source': contribution.source,
                        'timestamp': contribution.timestamp.isoformat(),
                        'total_harvest': str(total)
                    }
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            'live_board',
                            {
                                'type': 'new_contribution',
                                'data': ws_data
                            }
                        )
                except Exception:
                    pass
                # Notify the referrer their campaign got a new vote
            try:
                from dashboard.views import send_approval_push_notification
                send_approval_push_notification(contribution)
            except Exception as e:
                print(f"Failed to send approval push from webhook: {e}")
            
            # Notify admins of the new approved online payment
            try:
                from accounts.models import Member, WebPushSubscription
                from dashboard.views import send_web_push
                from django.db.models import Q
                admins = Member.objects.filter(
                    Q(role__in=['admin', 'approver']) | Q(is_superuser=True)
                )
                subs = WebPushSubscription.objects.filter(user__in=admins)
                for sub in subs:
                    send_web_push(sub, {
                        'title': 'New Online Payment 💳',
                        'body': f"{contribution.name} paid ₦{contribution.amount:,.0f} via Paystack.",
                        'url': '/dashboard/'
                    })
            except Exception as e:
                print(f"Failed to notify admins from webhook: {e}")

            return Response({'status': 'success'})

        return Response({'status': 'ignored', 'reason': 'Unhandled event'})
