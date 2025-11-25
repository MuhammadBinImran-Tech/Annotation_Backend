from django.contrib import admin
from .models import *

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'external_sku', 'category', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['name', 'external_sku', 'description']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'data_type', 'created_at']
    list_filter = ['data_type']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'service_name', 'model', 'is_active', 'created_at']
    list_filter = ['is_active', 'service_name']
    readonly_fields = ['created_at']

@admin.register(AnnotationBatch)
class AnnotationBatchAdmin(admin.ModelAdmin):
    list_display = ['name', 'batch_type', 'assigned_to', 'status', 'progress', 'batch_size', 'created_at']
    list_filter = ['batch_type', 'status', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(BatchItem)
class BatchItemAdmin(admin.ModelAdmin):
    list_display = ['batch', 'product', 'status', 'processed_by', 'started_at', 'completed_at']
    list_filter = ['status', 'batch__batch_type']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AISuggestion)
class AISuggestionAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'provider', 'suggested_value', 'confidence_score', 'created_at']
    list_filter = ['provider', 'attribute']
    readonly_fields = ['created_at']
    search_fields = ['product__name', 'attribute__name']

@admin.register(AIConsensus)
class AIConsensusAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'consensus_value', 'method', 'confidence', 'created_at']
    list_filter = ['method', 'attribute']
    readonly_fields = ['created_at']
    search_fields = ['product__name', 'attribute__name']

@admin.register(HumanAnnotation)
class HumanAnnotationAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'annotator', 'annotated_value', 'status', 'is_correction', 'created_at']
    list_filter = ['status', 'is_correction', 'annotator']
    readonly_fields = ['created_at', 'updated_at']
    search_fields = ['product__name', 'attribute__name', 'annotator__username']

@admin.register(FinalAttribute)
class FinalAttributeAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'final_value', 'source', 'decided_by', 'created_at']
    list_filter = ['source']
    readonly_fields = ['created_at']
    search_fields = ['product__name', 'attribute__name']