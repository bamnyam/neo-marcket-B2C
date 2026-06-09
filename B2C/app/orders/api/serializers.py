from rest_framework import serializers


class CheckoutItemSerializer(serializers.Serializer):
    sku_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    allowed_fields = {"idempotency_key", "items", "delivery_address"}

    idempotency_key = serializers.UUIDField()
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    delivery_address = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        unknown_fields = set(self.initial_data) - self.allowed_fields

        if unknown_fields:
            raise serializers.ValidationError("Unknown fields are not accepted")

        return attrs
