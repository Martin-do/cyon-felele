from rest_framework import generics
from django.shortcuts import render, get_object_or_404
import uuid
from .models import Contribution
from accounts.models import Member
from .serializers import ContributionSerializer

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Sum

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
import requests
from django.conf import settings

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
        referrer = get_object_or_404(Member, referral_slug=referral_slug)
        
        # Calculate leaderboard position
        # Get all members with the same contestant title
        if referrer.contestant_title and referrer.contestant_title != 'None':
            competitors = Member.objects.filter(is_active=True, is_staff=False, contestant_title=referrer.contestant_title)
            
            leaderboard = []
            for comp in competitors:
                comp_total = Contribution.objects.filter(referred_by=comp, is_voided=False, status='approved').aggregate(Sum('amount'))['amount__sum'] or 0.00
                leaderboard.append({'id': comp.id, 'total': comp_total})
                
                if comp.id == referrer.id:
                    total_amount = comp_total
                    
            leaderboard = sorted(leaderboard, key=lambda x: x['total'], reverse=True)
            
            top_3 = []
            for index, item in enumerate(leaderboard):
                if index < 3:
                    comp_member = Member.objects.get(id=item['id'])
                    top_3.append({
                        'rank': index + 1,
                        'name': comp_member.name,
                        'total': item['total'],
                        'picture_url': comp_member.profile_picture.url if comp_member.profile_picture else None,
                        'initial': comp_member.name[0].upper()
                    })

                if item['id'] == referrer.id:
                    leaderboard_position = index + 1
                    
        # Set a target amount for progress bars
        target_amount = 5000000 
        progress_percentage = min(int((total_amount / target_amount) * 100), 100)

        context = {
            'referrer': referrer,
            'idempotency_key': str(uuid.uuid4()),
            'leaderboard_position': leaderboard_position,
            'total_amount': total_amount,
            'top_3': top_3 if 'top_3' in locals() else [],
            'progress_percentage': progress_percentage,
            'target_amount': target_amount,
            'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
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
            data = res_data['data']
            amount = data['amount'] / 100.0  # Convert back from kobo

            referrer = None
            if referred_by_id:
                try:
                    referrer = Member.objects.get(id=referred_by_id)
                except Member.DoesNotExist:
                    pass

            # Check if contribution already exists for this reference (using idempotency_key = reference)
            contribution, created = Contribution.objects.get_or_create(
                idempotency_key=reference,
                defaults={
                    'name': name or 'Anonymous Paystack User',
                    'phone': phone,
                    'amount': amount,
                    'method': 'Paystack',
                    'source': 'guest_form',
                    'referred_by': referrer,
                    'is_anonymous': is_anonymous,
                    'status': 'approved'
                }
            )

            if created:
                # Trigger WebSocket push for Live Board
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
                
                async_to_sync(channel_layer.group_send)(
                    'live_board',
                    {
                        'type': 'new_contribution',
                        'data': ws_data
                    }
                )

            return Response({'id': str(contribution.id), 'status': 'success'})
            
        else:
            return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)
