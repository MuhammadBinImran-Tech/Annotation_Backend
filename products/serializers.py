from rest_framework import serializers
from django.contrib.auth.models import User, Group
from .models import *

class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']
    
    def get_role(self, obj):
        if obj.groups.filter(name='Admin').exists():
            return 'admin'
        elif obj.groups.filter(name='Annotator').exists():
            return 'annotator'
        return 'user'

class ProductSerializer(serializers.ModelSerializer):
    image_urls = serializers.ListField(child=serializers.URLField(), required=False)
    primary_image = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
    
    def get_primary_image(self, obj):
        if obj.image_urls and len(obj.image_urls) > 0:
            return obj.image_urls[0]
        return None

class AttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attribute
        fields = '__all__'

class AIProviderSerializer(serializers.ModelSerializer):
    api_key = serializers.SerializerMethodField()
    has_api_key = serializers.SerializerMethodField()
    
    class Meta:
        model = AIProvider
        fields = '__all__'
        extra_kwargs = {
            'config': {'write_only': False}
        }
    
    def get_api_key(self, obj):
        """Return masked API key when reading, or empty string if not set"""
        if obj.config and isinstance(obj.config, dict):
            api_key = obj.config.get('api_key', '')
            if api_key:
                # Mask the API key: show first 4 and last 4 characters
                if len(api_key) > 8:
                    return f"{api_key[:4]}...{api_key[-4:]}"
                return "****"
        return None
    
    def get_has_api_key(self, obj):
        """Check if API key is configured"""
        if obj.config and isinstance(obj.config, dict):
            return bool(obj.config.get('api_key'))
        return False
    
    def create(self, validated_data):
        """Create provider with API key from request data"""
        config = {}
        
        # Get API key and config from request data (not from validated_data as api_key is not in model)
        request = self.context.get('request')
        if request:
            # API key is required for creation
            if 'api_key' in request.data and request.data['api_key']:
                config['api_key'] = request.data['api_key']
            
            # Also preserve other config fields if they exist
            if 'max_tokens' in request.data:
                config['max_tokens'] = request.data.get('max_tokens', 1000)
            elif 'max_tokens' not in config:
                config['max_tokens'] = 1000
            
            if 'temperature' in request.data:
                config['temperature'] = request.data.get('temperature', 0.1)
            elif 'temperature' not in config:
                config['temperature'] = 0.1
        
        # Merge with any config from validated_data
        if 'config' in validated_data and isinstance(validated_data['config'], dict):
            config.update(validated_data['config'])
        
        validated_data['config'] = config
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update provider with API key from request data"""
        # Always start with existing config to preserve API key
        config = instance.config.copy() if instance.config and isinstance(instance.config, dict) else {}
        
        # Merge any config from validated_data (but don't overwrite api_key unless explicitly provided)
        if 'config' in validated_data and isinstance(validated_data['config'], dict):
            for key, val in validated_data['config'].items():
                if key != 'api_key':  # Don't overwrite API key from config field
                    config[key] = val
        
        # Get API key from request data
        request = self.context.get('request')
        if request:
            # Only update API key if a new one is explicitly provided
            if 'api_key' in request.data:
                api_key_value = request.data['api_key']
                if api_key_value and isinstance(api_key_value, str) and api_key_value.strip():
                    # Check if it's a masked key (contains ...)
                    if '...' not in api_key_value:
                        config['api_key'] = api_key_value.strip()
                    # If masked key, keep existing API key (already in config)
                # If empty string or None, keep existing API key (already in config)
            
            # Update other config fields if provided in request
            if 'max_tokens' in request.data:
                config['max_tokens'] = request.data.get('max_tokens', config.get('max_tokens', 1000))
            if 'temperature' in request.data:
                config['temperature'] = request.data.get('temperature', config.get('temperature', 0.1))
        
        validated_data['config'] = config
        return super().update(instance, validated_data)

class AISuggestionSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    data_type = serializers.CharField(source='attribute.data_type', read_only=True)
    allowed_values = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = AISuggestion
        fields = '__all__'
    
    def get_allowed_values(self, obj):
        return obj.attribute.allowed_values

class AIConsensusSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    data_type = serializers.CharField(source='attribute.data_type', read_only=True)
    allowed_values = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = AIConsensus
        fields = '__all__'
    
    def get_allowed_values(self, obj):
        return obj.attribute.allowed_values

class BatchItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='product', write_only=True)
    ai_suggestions = serializers.SerializerMethodField()
    ai_consensus = serializers.SerializerMethodField()
    human_annotations = serializers.SerializerMethodField()
    
    class Meta:
        model = BatchItem
        fields = '__all__'
    
    def get_ai_suggestions(self, obj):
        suggestions = AISuggestion.objects.filter(product=obj.product)
        return AISuggestionSerializer(suggestions, many=True).data
    
    def get_ai_consensus(self, obj):
        consensus = AIConsensus.objects.filter(product=obj.product)
        return AIConsensusSerializer(consensus, many=True).data
    
    def get_human_annotations(self, obj):
        annotations = HumanAnnotation.objects.filter(batch_item=obj)
        return HumanAnnotationSerializer(annotations, many=True).data

class AnnotationBatchSerializer(serializers.ModelSerializer):
    items = BatchItemSerializer(many=True, read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    item_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AnnotationBatch
        fields = '__all__'
    
    def get_item_count(self, obj):
        return obj.items.count()
    
    def get_completed_count(self, obj):
        return obj.items.filter(status='done').count()

class HumanAnnotationSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    annotator_name = serializers.CharField(source='annotator.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_images = serializers.SerializerMethodField()
    data_type = serializers.CharField(source='attribute.data_type', read_only=True)
    allowed_values = serializers.SerializerMethodField(read_only=True)
    ai_suggested_value = serializers.SerializerMethodField()
    
    class Meta:
        model = HumanAnnotation
        fields = '__all__'
    
    def get_product_images(self, obj):
        return obj.product.image_urls if obj.product.image_urls else []
    
    def get_allowed_values(self, obj):
        return obj.attribute.allowed_values
    
    def get_ai_suggested_value(self, obj):
        try:
            consensus = AIConsensus.objects.get(product=obj.product, attribute=obj.attribute)
            return consensus.consensus_value
        except AIConsensus.DoesNotExist:
            return None

class FinalAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    decided_by_name = serializers.CharField(source='decided_by.username', read_only=True)
    
    class Meta:
        model = FinalAttribute
        fields = '__all__'

class BatchAssignmentSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    annotator_ids = serializers.ListField(child=serializers.IntegerField())

class ProductDetailSerializer(serializers.ModelSerializer):
    ai_suggestions = serializers.SerializerMethodField()
    ai_consensus = serializers.SerializerMethodField()
    human_annotations = serializers.SerializerMethodField()
    final_attributes = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()
    batch_info = serializers.SerializerMethodField()
    overlap_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
    
    def get_ai_suggestions(self, obj):
        suggestions = AISuggestion.objects.filter(product=obj)
        return AISuggestionSerializer(suggestions, many=True).data
    
    def get_ai_consensus(self, obj):
        consensus = AIConsensus.objects.filter(product=obj)
        return AIConsensusSerializer(consensus, many=True).data
    
    def get_human_annotations(self, obj):
        annotations = HumanAnnotation.objects.filter(product=obj)
        return HumanAnnotationSerializer(annotations, many=True).data
    
    def get_final_attributes(self, obj):
        final_attrs = FinalAttribute.objects.filter(product=obj)
        return FinalAttributeSerializer(final_attrs, many=True).data
    
    def get_primary_image(self, obj):
        if obj.image_urls and len(obj.image_urls) > 0:
            return obj.image_urls[0]
        return None
    
    def get_batch_info(self, obj):
        batch_items = BatchItem.objects.filter(product=obj, batch__batch_type='human')
        if batch_items.exists():
            batch_item = batch_items.first()
            return {
                'batch_id': batch_item.batch.id,
                'batch_name': batch_item.batch.name,
                'batch_status': batch_item.batch.status,
                'item_status': batch_item.status
            }
        return None
    
    def get_overlap_data(self, obj):
        """Get overlapping annotations for admin review"""
        overlaps = OverlapComparison.objects.filter(product=obj, is_resolved=False)
        overlap_data = []
        for overlap in overlaps:
            annotations = overlap.annotations.all()
            overlap_data.append({
                'attribute': overlap.attribute.name,
                'annotations': HumanAnnotationSerializer(annotations, many=True).data,
                'overlap_id': overlap.id
            })
        return overlap_data

class AnnotationSubmitSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    attribute_id = serializers.IntegerField()
    annotated_value = serializers.CharField()
    batch_item_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['suggested', 'approved', 'rejected'])
    note = serializers.CharField(required=False, allow_blank=True)

class CreateBatchSerializer(serializers.Serializer):
    batch_size = serializers.IntegerField(default=10, min_value=1, max_value=50)

class AutoAssignSerializer(serializers.Serializer):
    batch_size = serializers.IntegerField(default=10)
    overlap_count = serializers.IntegerField(default=2, min_value=1, max_value=5)

class StartAutoAISerializer(serializers.Serializer):
    batch_size = serializers.IntegerField(default=10)

class OverlapResolutionSerializer(serializers.Serializer):
    overlap_id = serializers.IntegerField()
    resolved_value = serializers.CharField()
    attribute_id = serializers.IntegerField()
    product_id = serializers.IntegerField()

class BatchUnassignmentSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()

class ExportFinalAttributesSerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=['json', 'csv'], default='json')
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

class MissingValueFlagSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    annotator_name = serializers.CharField(source='annotator.username', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)
    
    class Meta:
        model = MissingValueFlag
        fields = '__all__'

class FlagValueSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    attribute_id = serializers.IntegerField()
    batch_item_id = serializers.IntegerField()
    requested_value = serializers.CharField()
    reason = serializers.CharField(required=False, allow_blank=True)