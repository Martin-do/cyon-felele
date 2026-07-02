from rest_framework import generics
from django.shortcuts import render, get_object_or_404, redirect
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

import hmac
import hashlib
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError

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

class ContributionCreateAPIView(generics.CreateAPIView):
    queryset = Contribution.objects.all()
    serializer_class = ContributionSerializer
    
    def perform_create(self, serializer):
        contribution = serializer.save()
        
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
        referral_slug = referral_slug.strip().strip('/')
        referrer = get_object_or_404(Member, referral_slug__iexact=referral_slug)
        if referral_slug != referrer.referral_slug:
            return redirect('contributions:referral_donation', referral_slug=referrer.referral_slug)
        
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
                        filter=Q(referrals__is_voided=False, referrals__status='approved')
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


@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(APIView):
    """
    Server-to-server webhook so a contribution still gets recorded even if the
    donor closes their browser before the frontend's VerifyPaystackPaymentView
    call completes. Uses the same idempotency_key=reference pattern, so this
    is safe to run alongside that view without creating duplicates.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Verify the request genuinely came from Paystack before trusting it
        paystack_signature = request.headers.get('X-Paystack-Signature', '')
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()

        if not paystack_signature or not hmac.compare_digest(computed_signature, paystack_signature):
            return HttpResponse(status=401)

        event = request.data
        event_type = event.get('event')

        if event_type == 'charge.success':
            data = event.get('data', {}) or {}
            reference = data.get('reference')

            if reference:
                amount = (data.get('amount', 0) - data.get('fees', 0) or data.get('amount', 0)) / 100.0

                metadata = data.get('metadata') or {}
                name = metadata.get('name') or 'Anonymous Paystack User'
                phone = metadata.get('phone')
                referred_by_id = metadata.get('referred_by')
                is_anonymous = metadata.get('is_anonymous') in ('true', True)

                referrer = None
                if referred_by_id:
                    try:
                        referrer = Member.objects.get(id=referred_by_id)
                    except (Member.DoesNotExist, ValueError):
                        pass

                try:
                    contribution, created = Contribution.objects.get_or_create(
                        idempotency_key=reference,
                        defaults={
                            'name': name,
                            'phone': phone,
                            'amount': amount,
                            'method': 'Online',
                            'source': 'guest_form',
                            'referred_by': referrer,
                            'is_anonymous': is_anonymous,
                            'status': 'approved'
                        }
                    )
                except (ValueError, ValidationError):
                    # reference wasn't a valid UUID for idempotency_key - nothing more we can do
                    contribution, created = None, False

                if created and contribution:
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
                        # Don't fail the webhook ack if the websocket push fails
                        pass

        # Always ack with 200 so Paystack doesn't keep retrying, even for events we don't act on
        return HttpResponse(status=200)
