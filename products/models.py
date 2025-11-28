from django.db import models
from django.db.models import Q, Max
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import json


class Category(models.Model):
    """Top-level taxonomy for products."""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    """Nested taxonomy scoped to a parent category."""
    id = models.BigAutoField(primary_key=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subcategories'
        ordering = ['category__name', 'name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f"{self.category.name} → {self.name}"

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
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
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

    def clean(self):
        if self.subcategory and not self.category:
            raise ValidationError("Subcategory cannot be set without a category.")
        if self.subcategory and self.category and self.subcategory.category_id != self.category_id:
            raise ValidationError("Subcategory must belong to the selected category.")

    def get_applicable_attributes(self, required_only: bool = False):
        """Return queryset of attributes relevant to this product."""
        return CategoryAttributeMapping.get_attributes_for_product(
            self,
            required_only=required_only
        )

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

    def clean(self):
        if self.data_type == 'enum' and self.allowed_values is not None:
            if not isinstance(self.allowed_values, list):
                raise ValidationError("Enum attributes must use a list of allowed values.")
            if not all(isinstance(value, str) for value in self.allowed_values):
                raise ValidationError("Enum allowed values must be strings.")

class CategoryAttributeMapping(models.Model):
    """Maps product categories/subcategories to relevant attributes."""
    id = models.BigAutoField(primary_key=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='attribute_mappings'
    )
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attribute_mappings'
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name='category_mappings'
    )
    is_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'category_attribute_mappings'
        ordering = ['category__name', 'subcategory__name', 'attribute__name']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'subcategory', 'attribute'],
                name='unique_category_subcategory_attribute'
            )
        ]
        indexes = [
            models.Index(fields=['category', 'subcategory'])
        ]

    def __str__(self):
        scope = self.subcategory.name if self.subcategory else 'All Subcategories'
        return f"{self.category.name} / {scope} -> {self.attribute.name}"

    def clean(self):
        if self.subcategory and self.subcategory.category_id != self.category_id:
            raise ValidationError("Subcategory must belong to the selected category.")

    @classmethod
    def _base_queryset(cls, category, required_only=False):
        if not category:
            return cls.objects.none()
        qs = cls.objects.filter(category=category)
        if required_only:
            qs = qs.filter(is_required=True)
        return qs

    @classmethod
    def _attribute_ids(cls, category, subcategory=None, required_only=False):
        qs = cls._base_queryset(category, required_only=required_only)
        if not qs.exists():
            return []

        attr_ids = set(
            qs.filter(subcategory__isnull=True)
            .values_list('attribute_id', flat=True)
        )

        if subcategory:
            sub_qs = qs.filter(subcategory=subcategory)
            attr_ids.update(sub_qs.values_list('attribute_id', flat=True))

        return list(attr_ids)

    @classmethod
    def get_attribute_ids_for_product(cls, product, required_only=False):
        if not product or not product.category:
            return []
        return cls._attribute_ids(
            category=product.category,
            subcategory=product.subcategory,
            required_only=required_only
        )

    @classmethod
    def get_attributes_for_product(cls, product, required_only=False):
        attr_ids = cls.get_attribute_ids_for_product(product, required_only=required_only)
        if attr_ids:
            return Attribute.objects.filter(id__in=attr_ids).order_by('name')
        # Fallback: if no mapping exists, return all attributes
        return Attribute.objects.all().order_by('name')

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
    progress = models.FloatField(default=0.0)
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
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'ai_consensus'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'attribute'],
                condition=Q(is_active=True),
                name='unique_active_ai_consensus'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"

    @classmethod
    def record(
        cls,
        *,
        product,
        attribute,
        consensus_value,
        method,
        confidence=None
    ):
        """Persist a new consensus version while keeping history."""
        cls.objects.filter(product=product, attribute=attribute, is_active=True).update(is_active=False)
        latest_version = cls.objects.filter(product=product, attribute=attribute).aggregate(
            max_version=Max('version')
        )['max_version'] or 0
        return cls.objects.create(
            product=product,
            attribute=attribute,
            consensus_value=consensus_value,
            method=method,
            confidence=confidence,
            version=latest_version + 1,
            is_active=True
        )

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
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'attribute', 'annotator', 'batch_item'],
                condition=Q(batch_item__isnull=False),
                name='unique_annotation_per_batch_item'
            )
        ]

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
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'final_attributes'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'attribute'],
                condition=Q(is_active=True),
                name='unique_active_final_attribute'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}"

    @classmethod
    def record(
        cls,
        *,
        product,
        attribute,
        final_value,
        source,
        decided_by=None,
        confidence_score=None
    ):
        """Persist a new final attribute version while deactivating previous ones."""
        cls.objects.filter(product=product, attribute=attribute, is_active=True).update(is_active=False)
        latest_version = cls.objects.filter(product=product, attribute=attribute).aggregate(
            max_version=Max('version')
        )['max_version'] or 0
        return cls.objects.create(
            product=product,
            attribute=attribute,
            final_value=final_value,
            source=source,
            decided_by=decided_by,
            confidence_score=confidence_score,
            version=latest_version + 1,
            is_active=True
        )

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
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'attribute', 'annotator', 'batch_item'],
                condition=Q(batch_item__isnull=False),
                name='unique_flag_per_batch_item'
            )
        ]

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

    def save(self, *args, **kwargs):
        if not self.pk:
            self.pk = 1
        super().save(*args, **kwargs)