from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Contribution

class ContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contribution
        fields = [
            'id', 'name', 'phone', 'amount', 'method', 
            'source', 'referred_by', 'recorder_id', 
            'proof_url', 'receipt_image', 'idempotency_key', 'is_anonymous', 'timestamp', 'status'
        ]
        read_only_fields = ['id', 'timestamp']

    def validate(self, attrs):
        name = attrs.get('name')
        amount = attrs.get('amount')
        source = attrs.get('source')
        receipt_image = attrs.get('receipt_image')
        idempotency_key = attrs.get('idempotency_key')
        
        if source in ['guest_form', 'member_hub'] and not receipt_image:
            raise serializers.ValidationError({"receipt_image": "Receipt upload is mandatory for online contributions."})
        
        if not idempotency_key or not Contribution.objects.filter(idempotency_key=idempotency_key).exists():
            time_threshold = timezone.now() - timedelta(minutes=15)
            duplicate_exists = Contribution.objects.filter(
                name__iexact=name, 
                amount=amount, 
                timestamp__gte=time_threshold
            ).exists()
            
            if duplicate_exists:
                raise serializers.ValidationError("A contribution of this exact amount was already recorded for this name in the last 15 minutes. If this is a separate donation, please add an initial or number to the name (e.g., 'John Doe 2').")
                
        return attrs

    def create(self, validated_data):
        idempotency_key = validated_data.get('idempotency_key')
        if idempotency_key:
            existing = Contribution.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        return super().create(validated_data)
