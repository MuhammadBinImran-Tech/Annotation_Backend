from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'attributes', AttributeViewSet, basename='attribute')
router.register(r'ai-providers', AIProviderViewSet, basename='aiprovider')
router.register(r'batches', AnnotationBatchViewSet, basename='batch')
router.register(r'batch-items', BatchItemViewSet, basename='batchitem')
router.register(r'annotations', HumanAnnotationViewSet, basename='annotation')
router.register(r'ai-suggestions', AISuggestionViewSet, basename='aisuggestion')
router.register(r'ai-consensus', AIConsensusViewSet, basename='aiconsensus')
router.register(r'final-attributes', FinalAttributeViewSet, basename='finalattribute')
router.register(r'overlaps', OverlapComparisonViewSet, basename='overlap')
router.register(r'missing-value-flags', MissingValueFlagViewSet, basename='missingvalueflag')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'ai-processing', AIProcessingViewSet, basename='aiprocessing')

urlpatterns = [
    path('', include(router.urls)),
]