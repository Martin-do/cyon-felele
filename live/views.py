from django.shortcuts import render
from django.db.models import Sum
from contributions.models import Contribution

def projector_board_view(request):
    total_harvest = Contribution.objects.filter(is_voided=False).aggregate(Sum('amount'))['amount__sum'] or 0.00
    recent_contributions = Contribution.objects.filter(is_voided=False).order_by('-timestamp')[:10]
    
    context = {
        'total_harvest': total_harvest,
        'recent_contributions': recent_contributions
    }
    return render(request, 'live/board.html', context)
