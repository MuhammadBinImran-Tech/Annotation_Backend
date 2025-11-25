from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
import json

class Product(models.Model):
    STATUS_CHOICES = [
        ('pending_ai', 'Pending AI'),
        ('ai_running', 'AI Running'),
        ('ai_done', 'AI Done'),
        ('assigned', 'Assigned to Annotator'),
        ('in_review', 'In Review'),
        ('reviewed', 'Reviewed'),
        ('finalized', 'Finalized'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    external_sku = models.CharField(max_length=120, unique=True, blank=True, null=True)
    name = models.TextField()
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=80, blank=True, null=True)
    subcategory = models.CharField(max_length=80, blank=True, null=True)
    image_urls = ArrayField(models.TextField(), blank=True, default=list)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_ai')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.external_sku})"

class Attribute(models.Model):
    DATA_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('enum', 'Enum'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    allowed_values = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attributes'
        ordering = ['name']

    def __str__(self):
        return self.name

class AIProvider(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    service_name = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_providers'

    def __str__(self):
        return f"{self.name} ({self.model})"

class AnnotationBatch(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    BATCH_TYPE_CHOICES = [
        ('ai', 'AI'),
        ('human', 'Human'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_batches')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    batch_type = models.CharField(max_length=20, choices=BATCH_TYPE_CHOICES)
    batch_size = models.IntegerField(default=10)
    parent_batch = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_batches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'annotation_batches'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class BatchItem(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    batch = models.ForeignKey(AnnotationBatch, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'batch_items'
        unique_together = ('batch', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.batch.name} - {self.product.name}"

class AISuggestion(models.Model):
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE)
    suggested_value = models.TextField()
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    raw_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_suggestions'
        unique_together = ('product', 'attribute', 'provider')

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name} - {self.provider.name}"

class AIConsensus(models.Model):
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    consensus_value = models.TextField()
    method = models.CharField(max_length=50)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_consensus'
        unique_together = ('product', 'attribute')

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"

class HumanAnnotation(models.Model):
    STATUS_CHOICES = [
        ('suggested', 'Suggested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    annotated_value = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='suggested')
    note = models.TextField(blank=True, null=True)
    batch_item = models.ForeignKey(BatchItem, on_delete=models.CASCADE, null=True, blank=True)
    is_correction = models.BooleanField(default=False)
    previous_value = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'human_annotations'
        unique_together = ('product', 'attribute', 'annotator', 'batch_item')

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name} - {self.annotator.username}"

class FinalAttribute(models.Model):
    SOURCE_CHOICES = [
        ('ai', 'AI'),
        ('human', 'Human'),
        ('consensus', 'Consensus'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    final_value = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'final_attributes'
        unique_together = ('product', 'attribute')

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"

class OverlapComparison(models.Model):
    """Tracks overlapping annotations for the same product-attribute by different annotators"""
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    annotations = models.ManyToManyField(HumanAnnotation)
    resolved_value = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'overlap_comparisons'
        unique_together = ('product', 'attribute')

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"

class MissingValueFlag(models.Model):
    """Tracks when annotators flag missing values that need to be added to the database"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    batch_item = models.ForeignKey(BatchItem, on_delete=models.CASCADE, null=True, blank=True)
    requested_value = models.TextField(help_text="The value the annotator wants to add")
    reason = models.TextField(blank=True, null=True, help_text="Why this value is needed")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_flags')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'missing_value_flags'
        unique_together = ('product', 'attribute', 'annotator', 'batch_item')

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name} - {self.requested_value}"

class AIProcessingControl(models.Model):
    """Controls AI processing state (pause/resume)"""
    id = models.BigAutoField(primary_key=True)
    is_paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_processing_control'
        verbose_name = 'AI Processing Control'
        verbose_name_plural = 'AI Processing Controls'

    def __str__(self):
        return f"AI Processing: {'Paused' if self.is_paused else 'Running'}"
    
    @classmethod
    def get_control(cls):
        """Get or create the singleton control instance"""
        control, _ = cls.objects.get_or_create(id=1)
        return control