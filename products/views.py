from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User, Group
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.db import transaction
import random
import threading
import time
from .models import *
from .serializers import *

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Admin').exists()

class IsAnnotator(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Annotator').exists()

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Admin').exists():
            return Product.objects.all()
        elif user.groups.filter(name='Annotator').exists():
            batch_items = BatchItem.objects.filter(
                batch__assigned_to=user,
                batch__status__in=['pending', 'in_progress']
            ).values_list('product_id', flat=True)
            return Product.objects.filter(id__in=batch_items)
        return Product.objects.none()

class AttributeViewSet(viewsets.ModelViewSet):
    queryset = Attribute.objects.all()
    serializer_class = AttributeSerializer
    permission_classes = [permissions.IsAuthenticated]

class AnnotationBatchViewSet(viewsets.ModelViewSet):
    queryset = AnnotationBatch.objects.all()
    serializer_class = AnnotationBatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Admin').exists():
            return AnnotationBatch.objects.all()
        elif user.groups.filter(name='Annotator').exists():
            return AnnotationBatch.objects.filter(assigned_to=user, batch_type='human')
        return AnnotationBatch.objects.none()
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def ai_batches(self, request):
        batches = AnnotationBatch.objects.filter(batch_type='ai')
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def human_batches(self, request):
        batches = AnnotationBatch.objects.filter(batch_type='human')
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def start_auto_ai_processing(self, request):
        """Start automated AI processing - processes all pending products in batches"""
        batch_size = request.data.get('batch_size', 10)
        
        if batch_size not in [10, 20]:
            return Response({"error": "batch_size must be 10 or 20"}, status=400)
        
        pending_count = Product.objects.filter(status='pending_ai').count()
        
        if pending_count == 0:
            return Response({"message": "No pending products for AI processing"}, status=400)
        
        # Start automated processing in background
        thread = threading.Thread(
            target=self.auto_process_all_batches,
            args=(batch_size,)
        )
        thread.daemon = True
        thread.start()
        
        return Response({
            "message": f"Automated AI processing started for {pending_count} products",
            "batch_size": batch_size,
            "estimated_batches": (pending_count + batch_size - 1) // batch_size
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def pause_ai_processing(self, request):
        """Pause automated AI processing"""
        from .models import AIProcessingControl
        control = AIProcessingControl.get_control()
        control.is_paused = True
        control.paused_at = timezone.now()
        control.paused_by = request.user
        control.save()
        return Response({
            "message": "AI processing paused successfully",
            "paused_at": control.paused_at
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def resume_ai_processing(self, request):
        """Resume automated AI processing"""
        from .models import AIProcessingControl
        control = AIProcessingControl.get_control()
        control.is_paused = False
        control.paused_at = None
        control.paused_by = None
        control.save()
        return Response({"message": "AI processing resumed successfully"})
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def create_ai_batch(self, request):
        """Create and process a single AI batch manually"""
        serializer = CreateBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        batch_size = serializer.validated_data['batch_size']
        
        pending_products = list(Product.objects.filter(status='pending_ai')[:batch_size])
        
        if not pending_products:
            return Response({"message": "No pending products for AI processing"}, status=400)
        
        batch = AnnotationBatch.objects.create(
            name=f"AI Batch - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            batch_type='ai',
            status='in_progress',
            batch_size=len(pending_products)
        )
        
        product_ids = [product.id for product in pending_products]
        
        for product in pending_products:
            BatchItem.objects.create(batch=batch, product=product)
        
        Product.objects.filter(id__in=product_ids).update(status='ai_running')
        
        # Start processing in background
        thread = threading.Thread(target=self.process_ai_batch, args=(batch.id, product_ids))
        thread.daemon = True
        thread.start()
        
        return Response({
            "message": f"AI batch started with {len(pending_products)} products",
            "batch_id": batch.id
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def create_human_batch(self, request):
        """Create a human review batch from AI-processed products"""
        serializer = CreateBatchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        batch_size = serializer.validated_data['batch_size']
        
        ai_done_products = list(Product.objects.filter(status='ai_done')[:batch_size])
        
        if not ai_done_products:
            return Response({"message": "No AI processed products available"}, status=400)
        
        batch = AnnotationBatch.objects.create(
            name=f"Annotator Review Batch - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            batch_type='human',
            status='pending',
            batch_size=len(ai_done_products)
        )
        
        product_ids = [product.id for product in ai_done_products]
        
        for product in ai_done_products:
            BatchItem.objects.create(batch=batch, product=product)
        
        Product.objects.filter(id__in=product_ids).update(status='assigned')
        
        return Response({
            "message": f"Annotator review batch created with {len(ai_done_products)} products",
            "batch_id": batch.id
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def assign_to_annotators(self, request, pk=None):
        """Assign a batch to multiple annotators (with overlap)"""
        try:
            batch = self.get_object()
            annotator_ids = request.data.get('annotator_ids', [])
            
            if not annotator_ids:
                return Response({"error": "annotator_ids is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            created_batches = []
            for annotator_id in annotator_ids:
                try:
                    annotator = User.objects.get(id=annotator_id, groups__name='Annotator')
                    
                    new_batch = AnnotationBatch.objects.create(
                        name=f"{batch.name} - {annotator.username}",
                        description=batch.description,
                        assigned_to=annotator,
                        batch_type='human',
                        status='pending',
                        batch_size=batch.batch_size,
                        parent_batch=batch,
                        progress=0.0  # Reset progress for new assignment
                    )
                    
                    for item in batch.items.all():
                        BatchItem.objects.create(
                            batch=new_batch,
                            product=item.product,
                            status='not_started'  # Reset to not_started
                        )
                    created_batches.append(new_batch.id)
                except User.DoesNotExist:
                    return Response({"error": f"Annotator with id {annotator_id} not found"}, status=status.HTTP_404_NOT_FOUND)
            
            batch.status = 'completed'
            batch.save()
            
            return Response({
                "message": f"Batches assigned successfully to {len(annotator_ids)} annotators",
                "created_batch_ids": created_batches
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def unassigned_batches(self, request):
        """Get all unassigned human batches"""
        batches = AnnotationBatch.objects.filter(batch_type='human', assigned_to__isnull=True, status='pending')
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def review_batch(self, request, pk=None):
        """Admin reviews and approves/rejects a completed batch"""
        batch = self.get_object()
        
        if batch.status != 'completed':
            return Response({
                "error": f"Batch must be completed before review. Current status: {batch.status}"
            }, status=400)
        
        action = request.data.get('action')  # 'approve' or 'reject'
        review_note = request.data.get('review_note', '')
        
        if action not in ['approve', 'reject']:
            return Response({
                "error": "action must be 'approve' or 'reject'"
            }, status=400)
        
        if action == 'approve':
            with transaction.atomic():
                # Mark all human annotations in this batch as 'approved'
                batch_items = batch.items.filter(status='done')
                for item in batch_items:
                    # Get all human annotations for this batch item
                    HumanAnnotation.objects.filter(
                        batch_item=item,
                        status='suggested'
                    ).update(status='approved')
                
                # Update all products in batch to 'reviewed' status if all batch items are done
                products_updated = 0
                for item in batch.items.all():
                    if item.status == 'done':
                        product = item.product
                        # Check if all annotators have completed (for overlap scenarios)
                        parent_batch = batch.parent_batch if batch.parent_batch else batch
                        related_batches = AnnotationBatch.objects.filter(
                            Q(id=parent_batch.id) | Q(parent_batch=parent_batch)
                        )
                        all_items = BatchItem.objects.filter(
                            product=product,
                            batch__in=related_batches,
                            batch__batch_type='human'
                        )
                        if all_items.filter(status='done').count() == all_items.count():
                            # Use BatchItemViewSet's validation method
                            batch_item_viewset = BatchItemViewSet()
                            if batch_item_viewset.validate_status_transition(product.status, 'reviewed'):
                                product.status = 'reviewed'
                                product.save()
                                products_updated += 1
                
                # Mark batch as reviewed and ready for finalization (keep status as completed)
                batch.status = 'completed'
                batch.save()
            
            return Response({
                "message": f"Batch {batch.name} approved successfully. {products_updated} product(s) are now ready for finalization.",
                "batch_id": batch.id,
                "products_ready_for_finalization": products_updated,
                "is_approved": True
            })
        else:
            # Reject - mark batch for rework
            with transaction.atomic():
                # Reset human annotations back to 'suggested' status
                batch_items = batch.items.all()
                for item in batch_items:
                    HumanAnnotation.objects.filter(
                        batch_item=item,
                        status='approved'
                    ).update(status='suggested')
                
                # Reset batch status
                batch.status = 'pending'
                batch.save()
                
                # Reset batch items to not_started
                batch.items.all().update(status='not_started', started_at=None, completed_at=None)
                
                # Reset batch progress
                batch.progress = 0.0
                batch.save()
                
                # Reset product statuses back to 'assigned' if they were in 'in_review' or 'reviewed'
                products_in_batch = Product.objects.filter(
                    id__in=batch.items.values_list('product_id', flat=True)
                )
                for product in products_in_batch:
                    if product.status in ['in_review', 'reviewed']:
                        batch_item_viewset = BatchItemViewSet()
                        if batch_item_viewset.validate_status_transition(product.status, 'assigned'):
                            product.status = 'assigned'
                            product.save()
            
            return Response({
                "message": f"Batch {batch.name} rejected and reset for rework",
                "batch_id": batch.id
            })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def auto_assign_to_annotators(self, request):
        """Automatically assign AI-processed products to annotators with overlap and workload balancing"""
        batch_size = request.data.get('batch_size', 10)
        overlap_count = request.data.get('overlap_count', 2)  # How many annotators per product
        
        if batch_size not in [10, 20]:
            return Response({"error": "batch_size must be 10 or 20"}, status=400)
        
        if overlap_count < 1 or overlap_count > 5:
            return Response({"error": "overlap_count must be between 1 and 5"}, status=400)
        
        # Get available annotators with workload information
        annotators = User.objects.filter(groups__name='Annotator')
        
        if not annotators.exists():
            return Response({"error": "No annotators available"}, status=400)
        
        # Calculate workload for each annotator
        annotator_workloads = []
        for annotator in annotators:
            active_items = BatchItem.objects.filter(
                batch__assigned_to=annotator,
                status__in=['not_started', 'in_progress']
            ).count()
            annotator_workloads.append({
                'annotator': annotator,
                'workload': active_items
            })
        
        # Sort by workload (ascending) to balance load
        annotator_workloads.sort(key=lambda x: x['workload'])
        
        # Get AI-processed products
        ai_done_products = list(Product.objects.filter(status='ai_done')[:batch_size])
        
        if not ai_done_products:
            return Response({"message": "No AI processed products available"}, status=400)
        
        # Create parent batch for tracking
        parent_batch = AnnotationBatch.objects.create(
            name=f"Auto-Assigned Batch - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            batch_type='human',
            status='pending',
            batch_size=len(ai_done_products)
        )
        
        for product in ai_done_products:
            BatchItem.objects.create(batch=parent_batch, product=product)
        
        # Assign products to annotators with proper overlap and load balancing
        created_batches = []
        annotator_batch_map = {}  # Track which annotators have batches
        
        # For each product, assign to different annotators (round-robin with overlap)
        for product_idx, product in enumerate(ai_done_products):
            # Select annotators for this product (ensuring overlap)
            # Use round-robin to distribute evenly
            selected_annotators_for_product = []
            for i in range(overlap_count):
                annotator_idx = (product_idx * overlap_count + i) % len(annotator_workloads)
                selected_annotator = annotator_workloads[annotator_idx]['annotator']
                
                if selected_annotator not in selected_annotators_for_product:
                    selected_annotators_for_product.append(selected_annotator)
            
            # Ensure we have enough annotators (if overlap_count > available annotators)
            while len(selected_annotators_for_product) < overlap_count and len(selected_annotators_for_product) < len(annotator_workloads):
                # Add annotators with lowest workload
                for workload_info in annotator_workloads:
                    if workload_info['annotator'] not in selected_annotators_for_product:
                        selected_annotators_for_product.append(workload_info['annotator'])
                        break
            
            # Create or get batch for each annotator
            for annotator in selected_annotators_for_product:
                if annotator not in annotator_batch_map:
                    new_batch = AnnotationBatch.objects.create(
                        name=f"Review Batch - {annotator.username} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                        assigned_to=annotator,
                        batch_type='human',
                        status='pending',
                        batch_size=0,  # Will be updated
                        parent_batch=parent_batch
                    )
                    annotator_batch_map[annotator] = new_batch
                    created_batches.append({
                        'batch_id': new_batch.id,
                        'annotator': annotator.username
                    })
                
                batch = annotator_batch_map[annotator]
                BatchItem.objects.create(
                    batch=batch,
                    product=product,
                    status='not_started'
                )
                batch.batch_size += 1
                batch.save()
        
        # Update product statuses
        product_ids = [p.id for p in ai_done_products]
        Product.objects.filter(id__in=product_ids).update(status='assigned')
        
        # Mark parent batch as completed
        parent_batch.status = 'completed'
        parent_batch.save()
        
        return Response({
            "message": f"Successfully assigned {len(ai_done_products)} products to {len(annotator_batch_map)} annotators",
            "parent_batch_id": parent_batch.id,
            "assigned_batches": created_batches
        })
    
    def auto_process_all_batches(self, batch_size):
        """Automatically process all pending products in batches"""
        from .models import AIProcessingControl
        try:
            while True:
                # Check if processing is paused
                control = AIProcessingControl.get_control()
                if control.is_paused:
                    print("AI processing is paused. Waiting...")
                    time.sleep(5)  # Check every 5 seconds
                    continue
                
                # Check for pending products with race condition protection
                with transaction.atomic():
                    pending_products = list(
                        Product.objects.select_for_update()
                        .filter(status='pending_ai')[:batch_size]
                    )
                    
                    if not pending_products:
                        print("No more pending products. Auto-processing completed.")
                        break
                    
                    product_ids = [product.id for product in pending_products]
                    
                    # Create batch
                    batch = AnnotationBatch.objects.create(
                        name=f"Auto AI Batch - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                        batch_type='ai',
                        status='in_progress',
                        batch_size=len(pending_products)
                    )
                    
                    for product in pending_products:
                        BatchItem.objects.create(batch=batch, product=product)
                    
                    # Update status atomically
                    Product.objects.filter(id__in=product_ids).update(status='ai_running')
                
                print(f"Processing batch {batch.id} with {len(pending_products)} products")
                
                # Process this batch synchronously
                self.simulate_ai_processing(batch.id, product_ids)
                
                # Small delay between batches
                time.sleep(1)
                
        except Exception as e:
            print(f"Error in auto_process_all_batches: {e}")
    
    def process_ai_batch(self, batch_id, product_ids):
        """Process AI batch with proper error handling"""
        try:
            thread = threading.Thread(target=self.simulate_ai_processing, args=(batch_id, product_ids))
            thread.daemon = True
            thread.start()
        except Exception as e:
            batch = AnnotationBatch.objects.get(id=batch_id)
            batch.status = 'completed'
            batch.progress = 100
            batch.save()
            print(f"AI processing error: {e}")
    
    def simulate_ai_processing(self, batch_id, product_ids):
        """Simulate AI processing - replace with actual AI calls"""
        try:
            batch = AnnotationBatch.objects.get(id=batch_id)
            products = Product.objects.filter(id__in=product_ids)
            
            attributes = list(Attribute.objects.all())
            ai_providers = list(AIProvider.objects.filter(is_active=True))
            
            print(f"Starting AI batch {batch_id} processing for {len(products)} products")
            
            for index, product in enumerate(products):
                print(f"Processing product {index+1}/{len(products)}: {product.name}")
                
                time.sleep(2)  # Simulate processing time
                
                for attribute in attributes:
                    for provider in ai_providers:
                        suggested_value = self.generate_ai_suggestion(product, attribute, provider)
                        confidence = round(random.uniform(0.7, 0.95), 4)
                        
                        AISuggestion.objects.create(
                            product=product,
                            attribute=attribute,
                            provider=provider,
                            suggested_value=suggested_value,
                            confidence_score=confidence,
                            raw_response={
                                'model': provider.model,
                                'suggestion': suggested_value,
                                'confidence': float(confidence)
                            }
                        )
                    
                    # Create consensus
                    suggestions = AISuggestion.objects.filter(product=product, attribute=attribute)
                    if suggestions:
                        consensus_value = self.build_consensus(suggestions)
                        AIConsensus.objects.create(
                            product=product,
                            attribute=attribute,
                            consensus_value=consensus_value,
                            method='weighted_majority',
                            confidence=round(random.uniform(0.8, 0.98), 4)
                        )
                
                product.status = 'ai_done'
                product.save()
                
                progress = ((index + 1) / len(products)) * 100
                batch.progress = progress
                batch.save()
                
                print(f"Completed product {index+1}/{len(products)} - Progress: {progress}%")
            
            batch.status = 'completed'
            batch.progress = 100
            batch.save()
            
            print(f"AI batch {batch_id} completed successfully")
            
        except Exception as e:
            try:
                batch = AnnotationBatch.objects.get(id=batch_id)
                batch.status = 'completed'
                batch.save()
            except:
                pass
            print(f"Background AI processing error: {e}")
    
    def generate_ai_suggestion(self, product, attribute, provider):
        """Generate realistic AI suggestions based on product information"""
        if attribute.name == 'Color':
            colors = ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow', 'Pink', 'Purple', 'Orange', 'Gray']
            return random.choice(colors)
        elif attribute.name == 'Size':
            sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
            return random.choice(sizes)
        elif attribute.name == 'Material':
            materials = ['Cotton', 'Polyester', 'Silk', 'Wool', 'Linen', 'Denim', 'Leather', 'Nylon']
            return random.choice(materials)
        elif attribute.name == 'Sleeve Length':
            sleeves = ['Short', 'Long', 'Sleeveless', 'Three-Quarter']
            return random.choice(sleeves)
        elif attribute.name == 'Gender':
            return random.choice(['Men', 'Women', 'Unisex'])
        elif attribute.name == 'Season':
            seasons = ['Spring', 'Summer', 'Fall', 'Winter', 'All Season']
            return random.choice(seasons)
        elif attribute.name == 'Pattern':
            patterns = ['Solid', 'Striped', 'Printed', 'Floral', 'Checkered', 'Plaid', 'Graphic']
            return random.choice(patterns)
        elif attribute.name == 'Fit':
            fits = ['Slim', 'Regular', 'Loose', 'Oversized', 'Skinny']
            return random.choice(fits)
        elif attribute.name == 'Neckline':
            necklines = ['Round', 'V-Neck', 'Collar', 'Boat Neck', 'Square']
            return random.choice(necklines)
        else:
            return f"AI suggested {attribute.name}"
    
    def build_consensus(self, suggestions):
        """Build consensus from multiple AI provider suggestions"""
        if not suggestions:
            return ""
        
        value_counts = {}
        for suggestion in suggestions:
            value = suggestion.suggested_value
            confidence = float(suggestion.confidence_score)
            value_counts[value] = value_counts.get(value, 0) + confidence
        
        return max(value_counts.items(), key=lambda x: x[1])[0]

class BatchItemViewSet(viewsets.ModelViewSet):
    queryset = BatchItem.objects.all()
    serializer_class = BatchItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Admin').exists():
            return BatchItem.objects.all()
        elif user.groups.filter(name='Annotator').exists():
            return BatchItem.objects.filter(batch__assigned_to=user)
        return BatchItem.objects.none()
    
    @action(detail=True, methods=['post'], permission_classes=[IsAnnotator])
    def start_work(self, request, pk=None):
        batch_item = self.get_object()
        if batch_item.status == 'not_started':
            batch_item.status = 'in_progress'
            batch_item.started_at = timezone.now()
            batch_item.processed_by = request.user
            batch_item.save()
            
            self.update_batch_progress(batch_item.batch)
            
            # Set product to in_review when work starts (validate transition)
            if self.validate_status_transition(batch_item.product.status, 'in_review'):
                batch_item.product.status = 'in_review'
                batch_item.product.save()
        
        serializer = self.get_serializer(batch_item)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAnnotator])
    def complete_work(self, request, pk=None):
        """FIXED: Complete work on a batch item and update product status correctly"""
        batch_item = self.get_object()
        
        if batch_item.status in ['not_started', 'in_progress']:
            with transaction.atomic():
                # Mark batch item as done
                batch_item.status = 'done'
                batch_item.completed_at = timezone.now()
                batch_item.processed_by = request.user
                batch_item.save()
                
                # Update batch progress
                self.update_batch_progress(batch_item.batch)
                
                # Check if all items in THIS batch are complete
                batch = batch_item.batch
                if batch.items.filter(status='done').count() == batch.items.count():
                    batch.status = 'completed'
                    batch.save()
                    
                    # Automatically approve all annotations in this completed batch
                    batch_items = batch.items.filter(status='done')
                    for item in batch_items:
                        HumanAnnotation.objects.filter(
                            batch_item=item,
                            status='suggested'
                        ).update(status='approved')
                
                # CRITICAL FIX: Check if the product has been reviewed by ALL assigned annotators
                # Only count batch items from the CURRENT annotation round (same parent batch or related batches)
                product = batch_item.product
                current_batch = batch_item.batch
                
                # Find the parent batch if this is a child batch, or use current batch as parent
                parent_batch = current_batch.parent_batch if current_batch.parent_batch else current_batch
                
                # Get all child batches from the same parent (for overlap scenarios)
                # OR if no parent, get batches created around the same time for this product
                if parent_batch:
                    related_batches = AnnotationBatch.objects.filter(
                        Q(id=parent_batch.id) | Q(parent_batch=parent_batch)
                    )
                else:
                    # For batches without parent, find batches created within 1 hour of this batch
                    time_window = current_batch.created_at - timezone.timedelta(hours=1)
                    related_batches = AnnotationBatch.objects.filter(
                        Q(id=current_batch.id) |
                        Q(created_at__gte=time_window, created_at__lte=current_batch.created_at + timezone.timedelta(hours=1))
                    )
                
                # Find all batch items for this product in related batches
                all_batch_items_for_product = BatchItem.objects.filter(
                    product=product,
                    batch__in=related_batches,
                    batch__batch_type='human',
                    batch__assigned_to__isnull=False  # Only count assigned batches
                )
                
                # Count how many are completed
                completed_items = all_batch_items_for_product.filter(status='done').count()
                total_items = all_batch_items_for_product.count()
                
                # If ALL annotators have completed their review, mark as reviewed
                if total_items > 0 and completed_items == total_items:
                    # Validate status transition
                    if self.validate_status_transition(product.status, 'reviewed'):
                        product.status = 'reviewed'
                        product.save()
                        
                        # Also check for overlaps
                        self.check_for_overlaps(product)
                elif completed_items > 0:
                    # At least one review is done, but not all
                    if self.validate_status_transition(product.status, 'in_review'):
                        product.status = 'in_review'
                        product.save()
        
        serializer = self.get_serializer(batch_item)
        return Response(serializer.data)
    
    def update_batch_progress(self, batch):
        """Update batch progress percentage"""
        total_items = batch.items.count()
        completed_items = batch.items.filter(status='done').count()
        if total_items > 0:
            batch.progress = (completed_items / total_items) * 100
            batch.save()
    
    def validate_status_transition(self, current_status, new_status):
        """Validate if status transition is allowed"""
        ALLOWED_TRANSITIONS = {
            'pending_ai': ['ai_running'],
            'ai_running': ['ai_done'],
            'ai_done': ['assigned'],
            'assigned': ['in_review'],
            'in_review': ['reviewed', 'assigned'],  # Can go back to assigned if needed
            'reviewed': ['finalized'],
            'finalized': []  # Terminal state
        }
        
        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        return new_status in allowed
    
    def check_for_overlaps(self, product):
        """Check if multiple annotators have worked on the same product"""
        human_annotations = HumanAnnotation.objects.filter(product=product, status='approved')
        
        annotations_by_attribute = {}
        for annotation in human_annotations:
            attr_id = annotation.attribute_id
            if attr_id not in annotations_by_attribute:
                annotations_by_attribute[attr_id] = []
            annotations_by_attribute[attr_id].append(annotation)
        
        for attr_id, annotations in annotations_by_attribute.items():
            if len(annotations) > 1:
                values = set(ann.annotated_value for ann in annotations)
                if len(values) > 1:
                    overlap, created = OverlapComparison.objects.get_or_create(
                        product=product,
                        attribute_id=attr_id,
                        defaults={'is_resolved': False}
                    )
                    overlap.annotations.set(annotations)
                    overlap.save()

class HumanAnnotationViewSet(viewsets.ModelViewSet):
    queryset = HumanAnnotation.objects.all()
    serializer_class = HumanAnnotationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Admin').exists():
            return HumanAnnotation.objects.all()
        elif user.groups.filter(name='Annotator').exists():
            return HumanAnnotation.objects.filter(annotator=user)
        return HumanAnnotation.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(annotator=self.request.user)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAnnotator])
    def submit_annotation(self, request):
        serializer = AnnotationSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                product = Product.objects.get(id=data['product_id'])
                attribute = Attribute.objects.get(id=data['attribute_id'])
                batch_item = BatchItem.objects.get(id=data['batch_item_id'])
                
                annotation, created = HumanAnnotation.objects.get_or_create(
                    product=product,
                    attribute=attribute,
                    annotator=request.user,
                    batch_item=batch_item,
                    defaults={
                        'annotated_value': data['annotated_value'],
                        'status': data['status'],
                        'note': data.get('note', '')
                    }
                )
                
                if not created:
                    annotation.annotated_value = data['annotated_value']
                    annotation.status = data['status']
                    annotation.note = data.get('note', '')
                    annotation.save()
                
                try:
                    ai_consensus = AIConsensus.objects.get(product=product, attribute=attribute)
                    if ai_consensus.consensus_value != data['annotated_value']:
                        annotation.is_correction = True
                        annotation.previous_value = ai_consensus.consensus_value
                        annotation.save()
                except AIConsensus.DoesNotExist:
                    pass
                
                # Check for overlaps immediately when annotation is submitted
                # This allows admin to see conflicts early
                self.check_for_overlaps_early(product, attribute)
                
                return Response({
                    "message": "Annotation submitted successfully",
                    "annotation_id": annotation.id
                })
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def check_for_overlaps_early(self, product, attribute):
        """Check for overlaps as soon as annotations are submitted"""
        # Get all approved annotations for this product-attribute
        annotations = HumanAnnotation.objects.filter(
            product=product,
            attribute=attribute,
            status='approved'
        )
        
        if annotations.count() > 1:
            values = set(ann.annotated_value for ann in annotations)
            if len(values) > 1:
                # There's a conflict - create or update overlap record
                overlap, created = OverlapComparison.objects.get_or_create(
                    product=product,
                    attribute=attribute,
                    defaults={'is_resolved': False}
                )
                overlap.annotations.set(annotations)
                overlap.save()
    
    @action(detail=False, methods=['get'])
    def by_product(self, request):
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({"error": "product_id parameter is required"}, status=400)
        
        annotations = HumanAnnotation.objects.filter(product_id=product_id)
        serializer = self.get_serializer(annotations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_batch_item(self, request):
        batch_item_id = request.query_params.get('batch_item_id')
        if not batch_item_id:
            return Response({"error": "batch_item_id parameter is required"}, status=400)
        
        annotations = HumanAnnotation.objects.filter(batch_item_id=batch_item_id)
        serializer = self.get_serializer(annotations, many=True)
        return Response(serializer.data)

class AISuggestionViewSet(viewsets.ModelViewSet):
    queryset = AISuggestion.objects.all()
    serializer_class = AISuggestionSerializer
    permission_classes = [permissions.IsAuthenticated]

class AIConsensusViewSet(viewsets.ModelViewSet):
    queryset = AIConsensus.objects.all()
    serializer_class = AIConsensusSerializer
    permission_classes = [permissions.IsAuthenticated]

class FinalAttributeViewSet(viewsets.ModelViewSet):
    queryset = FinalAttribute.objects.all()
    serializer_class = FinalAttributeSerializer
    permission_classes = [permissions.IsAuthenticated & IsAdmin]
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def finalize_attributes(self, request):
        """FIXED: Finalize attributes for reviewed products (can finalize single or batch)"""
        product_id = request.data.get('product_id')
        batch_id = request.data.get('batch_id')
        
        try:
            with transaction.atomic():
                products_to_finalize = []
                
                if product_id:
                    # Finalize single product
                    product = Product.objects.get(id=product_id)
                    if product.status != 'reviewed':
                        return Response({
                            "error": f"Product must be in 'reviewed' status. Current status: {product.status}"
                        }, status=400)
                    products_to_finalize.append(product)
                    
                elif batch_id:
                    # Finalize all reviewed products in a batch
                    batch = AnnotationBatch.objects.get(id=batch_id)
                    batch_product_ids = batch.items.values_list('product_id', flat=True)
                    products_to_finalize = Product.objects.filter(
                        id__in=batch_product_ids,
                        status='reviewed'
                    )
                    
                    if not products_to_finalize:
                        return Response({
                            "error": "No reviewed products found in this batch"
                        }, status=400)
                else:
                    return Response({
                        "error": "Either product_id or batch_id is required"
                    }, status=400)
                
                finalized_count = 0
                finalized_products = []
                errors = []
                
                for product in products_to_finalize:
                    # If product is in 'reviewed' status, automatically approve any 'suggested' annotations
                    # This handles cases where annotations weren't auto-approved when batch was completed
                    if product.status == 'reviewed':
                        HumanAnnotation.objects.filter(
                            product=product,
                            status='suggested'
                        ).update(status='approved')
                    
                    # Get all approved human annotations for this product
                    human_annotations = HumanAnnotation.objects.filter(
                        product=product,
                        status='approved'
                    )
                    
                    if not human_annotations.exists():
                        # Check if there are any annotations at all
                        all_annotations = HumanAnnotation.objects.filter(product=product)
                        if all_annotations.exists():
                            errors.append(f"Product '{product.name}' has annotations but none are approved. Please ensure the batch is completed.")
                        else:
                            errors.append(f"Product '{product.name}' has no annotations. Please ensure annotators have completed their work.")
                        continue
                    
                    # Validate that all required attributes are annotated
                    required_attributes = Attribute.objects.all()
                    annotated_attribute_ids = set(human_annotations.values_list('attribute_id', flat=True))
                    missing_attributes = required_attributes.exclude(id__in=annotated_attribute_ids)
                    
                    if missing_attributes.exists():
                        missing_names = list(missing_attributes.values_list('name', flat=True))
                        errors.append(f"Product '{product.name}' - missing annotations for attributes: {', '.join(missing_names)}")
                        continue
                    
                    # Group annotations by attribute
                    annotations_by_attr = {}
                    for annotation in human_annotations:
                        attr_id = annotation.attribute_id
                        if attr_id not in annotations_by_attr:
                            annotations_by_attr[attr_id] = []
                        annotations_by_attr[attr_id].append(annotation)
                    
                    # Finalize each attribute
                    for attr_id, annotations in annotations_by_attr.items():
                        # If multiple annotators reviewed, take consensus or most common value
                        if len(annotations) > 1:
                            # Count values
                            value_counts = {}
                            for ann in annotations:
                                value_counts[ann.annotated_value] = value_counts.get(ann.annotated_value, 0) + 1
                            
                            # Get most common value
                            final_value = max(value_counts.items(), key=lambda x: x[1])[0]
                            source = 'consensus'
                        else:
                            final_value = annotations[0].annotated_value
                            source = 'human'
                        
                        # Create or update final attribute
                        final_attr, created = FinalAttribute.objects.update_or_create(
                            product=product,
                            attribute_id=attr_id,
                            defaults={
                                'final_value': final_value,
                                'source': source,
                                'decided_by': request.user,
                                'confidence_score': 1.0
                            }
                        )
                    
                    # Mark product as finalized
                    product.status = 'finalized'
                    product.save()
                    
                    finalized_count += 1
                    finalized_products.append({
                        'product_id': product.id,
                        'product_name': product.name
                    })
                
                if finalized_count == 0:
                    error_message = "No products were finalized."
                    if errors:
                        error_message += "\n\n" + "\n".join(errors)
                    else:
                        error_message += " Ensure they have approved annotations and are in 'reviewed' status."
                    return Response({
                        "error": error_message,
                        "details": errors
                    }, status=400)
                
                return Response({
                    "message": f"Successfully finalized {finalized_count} product(s)",
                    "finalized_count": finalized_count,
                    "products": finalized_products
                })
                
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)
        except AnnotationBatch.DoesNotExist:
            return Response({"error": "Batch not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def reviewable_products(self, request):
        """Get all products that are ready for finalization (reviewed status)"""
        reviewed_products = Product.objects.filter(status='reviewed')
        serializer = ProductSerializer(reviewed_products, many=True)
        return Response({
            "count": reviewed_products.count(),
            "products": serializer.data
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def finalize_all_reviewed(self, request):
        """Finalize all products in reviewed status"""
        try:
            with transaction.atomic():
                reviewed_products = Product.objects.filter(status='reviewed')
                
                if not reviewed_products.exists():
                    return Response({
                        "message": "No reviewed products to finalize"
                    }, status=200)
                
                finalized_count = 0
                finalized_products = []
                errors = []
                
                for product in reviewed_products:
                    # Get all approved human annotations for this product
                    human_annotations = HumanAnnotation.objects.filter(
                        product=product,
                        status='approved'
                    )
                    
                    if not human_annotations.exists():
                        all_annotations = HumanAnnotation.objects.filter(product=product)
                        if all_annotations.exists():
                            errors.append(f"Product '{product.name}' has annotations but none are approved.")
                        else:
                            errors.append(f"Product '{product.name}' has no annotations.")
                        continue
                    
                    # Validate that all required attributes are annotated
                    required_attributes = Attribute.objects.all()
                    annotated_attribute_ids = set(human_annotations.values_list('attribute_id', flat=True))
                    missing_attributes = required_attributes.exclude(id__in=annotated_attribute_ids)
                    
                    if missing_attributes.exists():
                        missing_names = list(missing_attributes.values_list('name', flat=True))
                        errors.append(f"Product '{product.name}' - missing annotations for attributes: {', '.join(missing_names)}")
                        continue
                    
                    # Group annotations by attribute
                    annotations_by_attr = {}
                    for annotation in human_annotations:
                        attr_id = annotation.attribute_id
                        if attr_id not in annotations_by_attr:
                            annotations_by_attr[attr_id] = []
                        annotations_by_attr[attr_id].append(annotation)
                    
                    # Finalize each attribute
                    for attr_id, annotations in annotations_by_attr.items():
                        # If multiple annotators reviewed, take consensus
                        if len(annotations) > 1:
                            value_counts = {}
                            for ann in annotations:
                                value_counts[ann.annotated_value] = value_counts.get(ann.annotated_value, 0) + 1
                            final_value = max(value_counts.items(), key=lambda x: x[1])[0]
                            source = 'consensus'
                        else:
                            final_value = annotations[0].annotated_value
                            source = 'human'
                        
                        FinalAttribute.objects.update_or_create(
                            product=product,
                            attribute_id=attr_id,
                            defaults={
                                'final_value': final_value,
                                'source': source,
                                'decided_by': request.user,
                                'confidence_score': 1.0
                            }
                        )
                    
                    product.status = 'finalized'
                    product.save()
                    
                    finalized_count += 1
                    finalized_products.append({
                        'product_id': product.id,
                        'product_name': product.name
                    })
                
                response_data = {
                    "message": f"Successfully finalized {finalized_count} product(s)",
                    "finalized_count": finalized_count,
                    "products": finalized_products
                }
                
                if errors:
                    response_data["warnings"] = errors
                    response_data["message"] += f". {len(errors)} product(s) could not be finalized."
                
                return Response(response_data)
                
        except Exception as e:
            return Response({"error": str(e)}, status=500)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def export(self, request):
        """Export final attributes in JSON or CSV format"""
        from django.http import HttpResponse
        import json
        import csv
        from io import StringIO
        
        format_type = request.data.get('format', 'json')
        product_ids = request.data.get('product_ids', [])
        
        if product_ids:
            final_attrs = FinalAttribute.objects.filter(product_id__in=product_ids)
        else:
            final_attrs = FinalAttribute.objects.all()
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="final_attributes.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Product ID', 'Product Name', 'Attribute', 'Final Value', 'Source', 'Decided By', 'Confidence'])
            
            for attr in final_attrs:
                writer.writerow([
                    attr.product.id,
                    attr.product.name,
                    attr.attribute.name,
                    attr.final_value,
                    attr.source,
                    attr.decided_by.username if attr.decided_by else '',
                    float(attr.confidence_score) if attr.confidence_score else ''
                ])
            
            return response
        else:
            # JSON format
            data = []
            for attr in final_attrs:
                data.append({
                    'product_id': attr.product.id,
                    'product_name': attr.product.name,
                    'attribute_id': attr.attribute.id,
                    'attribute_name': attr.attribute.name,
                    'final_value': attr.final_value,
                    'source': attr.source,
                    'decided_by': attr.decided_by.username if attr.decided_by else None,
                    'confidence_score': float(attr.confidence_score) if attr.confidence_score else None,
                    'created_at': attr.created_at.isoformat()
                })
            
            response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
            response['Content-Disposition'] = 'attachment; filename="final_attributes.json"'
            return response
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def resolve_overlap(self, request):
        """Resolve overlapping annotations"""
        serializer = OverlapResolutionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                overlap = OverlapComparison.objects.get(
                    id=data['overlap_id'],
                    product_id=data['product_id'],
                    attribute_id=data['attribute_id']
                )
                
                final_attr, created = FinalAttribute.objects.get_or_create(
                    product=overlap.product,
                    attribute=overlap.attribute,
                    defaults={
                        'final_value': data['resolved_value'],
                        'source': 'consensus',
                        'decided_by': request.user,
                        'confidence_score': 0.95
                    }
                )
                
                if not created:
                    final_attr.final_value = data['resolved_value']
                    final_attr.source = 'consensus'
                    final_attr.decided_by = request.user
                    final_attr.save()
                
                overlap.resolved_value = data['resolved_value']
                overlap.resolved_by = request.user
                overlap.resolved_at = timezone.now()
                overlap.is_resolved = True
                overlap.save()
                
                return Response({"message": "Overlap resolved successfully"})
                
        except OverlapComparison.DoesNotExist:
            return Response({"error": "Overlap record not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class OverlapComparisonViewSet(viewsets.ModelViewSet):
    queryset = OverlapComparison.objects.all()
    serializer_class = serializers.Serializer
    permission_classes = [permissions.IsAuthenticated & IsAdmin]
    
    @action(detail=False, methods=['get'])
    def unresolved(self, request):
        """Get all unresolved overlaps for admin review"""
        overlaps = OverlapComparison.objects.filter(is_resolved=False)
        result = []
        for overlap in overlaps:
            annotations = overlap.annotations.all()
            result.append({
                'id': overlap.id,
                'product': overlap.product.name,
                'product_id': overlap.product.id,
                'attribute': overlap.attribute.name,
                'attribute_id': overlap.attribute.id,
                'annotations': HumanAnnotationSerializer(annotations, many=True).data,
                'created_at': overlap.created_at
            })
        return Response(result)

class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        user = request.user
        
        if user.groups.filter(name='Admin').exists():
            # FIXED: Admin dashboard stats with correct counting
            total_products = Product.objects.count()
            pending_ai_products = Product.objects.filter(status='pending_ai').count()
            ai_running_products = Product.objects.filter(status='ai_running').count()
            ai_done_products = Product.objects.filter(status='ai_done').count()
            assigned_products = Product.objects.filter(status='assigned').count()
            in_review_products = Product.objects.filter(status='in_review').count()
            reviewed_products = Product.objects.filter(status='reviewed').count()
            finalized_products = Product.objects.filter(status='finalized').count()
            
            total_batches = AnnotationBatch.objects.count()
            pending_batches = AnnotationBatch.objects.filter(status='pending').count()
            in_progress_batches = AnnotationBatch.objects.filter(status='in_progress').count()
            completed_batches = AnnotationBatch.objects.filter(status='completed').count()
            
            ai_batches = AnnotationBatch.objects.filter(batch_type='ai').count()
            human_batches = AnnotationBatch.objects.filter(batch_type='human').count()
            
            # Overlap statistics
            total_overlaps = OverlapComparison.objects.count()
            resolved_overlaps = OverlapComparison.objects.filter(is_resolved=True).count()
            unresolved_overlaps = total_overlaps - resolved_overlaps
            
            annotators = User.objects.filter(groups__name='Annotator')
            annotator_stats = []
            for annotator in annotators:
                completed_items = BatchItem.objects.filter(processed_by=annotator, status='done').count()
                total_assigned = BatchItem.objects.filter(batch__assigned_to=annotator).count()
                accuracy_data = self.calculate_annotator_accuracy(annotator)
                
                annotator_stats.append({
                    'id': annotator.id,
                    'username': annotator.username,
                    'completed_items': completed_items,
                    'total_assigned': total_assigned,
                    'completion_rate': (completed_items / total_assigned * 100) if total_assigned > 0 else 0,
                    'accuracy_rate': accuracy_data['accuracy_rate'],
                    'change_rate': accuracy_data['change_rate'],
                    'items_per_hour': accuracy_data['items_per_hour']
                })
            
            # Calculate AI metrics
            # Products with AI processing (have AI suggestions or consensus)
            total_products_with_ai = Product.objects.filter(
                Q(aisuggestion__isnull=False) | Q(aiconsensus__isnull=False)
            ).distinct().count()
            
            # AI coverage: percentage of total products that have AI processing
            ai_coverage = (total_products_with_ai / total_products * 100) if total_products > 0 else 0
            
            # AI accuracy: compare AI consensus with human annotations
            # Get all product-attribute pairs where both AI consensus and human annotations exist
            ai_consensus_attrs = set(AIConsensus.objects.values_list('product_id', 'attribute_id').distinct())
            human_annotation_attrs = set(HumanAnnotation.objects.values_list('product_id', 'attribute_id').distinct())
            
            # Find overlapping product-attribute pairs
            overlapping_pairs = ai_consensus_attrs & human_annotation_attrs
            ai_total_compared = len(overlapping_pairs)
            ai_matches = 0
            
            for product_id, attribute_id in overlapping_pairs:
                try:
                    ai_consensus = AIConsensus.objects.get(product_id=product_id, attribute_id=attribute_id)
                    human_annotations = HumanAnnotation.objects.filter(
                        product_id=product_id, 
                        attribute_id=attribute_id
                    )
                    # Check if any human annotation matches AI consensus
                    for human_ann in human_annotations:
                        if human_ann.annotated_value.strip().lower() == ai_consensus.consensus_value.strip().lower():
                            ai_matches += 1
                            break
                except AIConsensus.DoesNotExist:
                    pass
            
            ai_accuracy = (ai_matches / ai_total_compared * 100) if ai_total_compared > 0 else 0
            
            return Response({
                'products': {
                    'total': total_products,
                    'pending_ai': pending_ai_products,
                    'ai_running': ai_running_products,
                    'ai_done': ai_done_products,
                    'assigned': assigned_products,
                    'in_review': in_review_products,
                    'reviewed': reviewed_products,
                    'finalized': finalized_products
                },
                'batches': {
                    'total': total_batches,
                    'pending': pending_batches,
                    'in_progress': in_progress_batches,
                    'completed': completed_batches,
                    'ai_batches': ai_batches,
                    'human_batches': human_batches
                },
                'overlaps': {
                    'total': total_overlaps,
                    'resolved': resolved_overlaps,
                    'unresolved': unresolved_overlaps
                },
                'annotators': annotator_stats,
                'ai_metrics': {
                    'coverage': round(ai_coverage, 2),
                    'accuracy': round(ai_accuracy, 2),
                    'total_products_processed': total_products_with_ai,
                    'comparisons_made': ai_total_compared
                }
            })
        
        elif user.groups.filter(name='Annotator').exists():
            # Annotator dashboard stats
            assigned_batches = AnnotationBatch.objects.filter(assigned_to=user, batch_type='human')
            total_assigned = BatchItem.objects.filter(batch__assigned_to=user).count()
            completed_items = BatchItem.objects.filter(batch__assigned_to=user, status='done').count()
            in_progress_items = BatchItem.objects.filter(batch__assigned_to=user, status='in_progress').count()
            not_started_items = BatchItem.objects.filter(batch__assigned_to=user, status='not_started').count()
            
            # Recent activity
            recent_annotations = HumanAnnotation.objects.filter(
                annotator=user
            ).order_by('-created_at')[:10]
            recent_serializer = HumanAnnotationSerializer(recent_annotations, many=True)
            
            return Response({
                'assigned_batches': assigned_batches.count(),
                'total_items': total_assigned,
                'completed_items': completed_items,
                'in_progress_items': in_progress_items,
                'not_started_items': not_started_items,
                'completion_rate': (completed_items / total_assigned * 100) if total_assigned > 0 else 0,
                'recent_activity': recent_serializer.data
            })
        
        return Response({})
    
    def calculate_annotator_accuracy(self, annotator):
        """Calculate annotator accuracy, change rate, and speed compared to AI"""
        annotations = HumanAnnotation.objects.filter(annotator=annotator, status='approved')
        total_annotations = annotations.count()
        
        if total_annotations == 0:
            return {'accuracy_rate': 0, 'change_rate': 0, 'items_per_hour': 0}
        
        corrections = 0
        changes = 0
        
        # Calculate speed (items per hour)
        completed_items = BatchItem.objects.filter(
            processed_by=annotator,
            status='done',
            completed_at__isnull=False,
            started_at__isnull=False
        )
        
        total_time_seconds = 0
        for item in completed_items:
            if item.started_at and item.completed_at:
                time_diff = (item.completed_at - item.started_at).total_seconds()
                total_time_seconds += time_diff
        
        # Calculate items per hour
        if total_time_seconds > 0:
            items_per_hour = (completed_items.count() / total_time_seconds) * 3600
        else:
            items_per_hour = 0
        
        for annotation in annotations:
            try:
                ai_consensus = AIConsensus.objects.get(
                    product=annotation.product,
                    attribute=annotation.attribute
                )
                if ai_consensus.consensus_value != annotation.annotated_value:
                    changes += 1
                    corrections += 1
            except AIConsensus.DoesNotExist:
                pass
        
        accuracy_rate = ((total_annotations - corrections) / total_annotations * 100) if total_annotations > 0 else 0
        change_rate = (changes / total_annotations * 100) if total_annotations > 0 else 0
        
        return {
            'accuracy_rate': round(accuracy_rate, 2),
            'change_rate': round(change_rate, 2),
            'items_per_hour': round(items_per_hour, 2)
        }

class MissingValueFlagViewSet(viewsets.ModelViewSet):
    queryset = MissingValueFlag.objects.all()
    serializer_class = MissingValueFlagSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='Admin').exists():
            return MissingValueFlag.objects.all()
        elif user.groups.filter(name='Annotator').exists():
            return MissingValueFlag.objects.filter(annotator=user)
        return MissingValueFlag.objects.none()
    
    @action(detail=False, methods=['post'], permission_classes=[IsAnnotator])
    def flag_value(self, request):
        """Flag a missing value that needs to be added to the database"""
        serializer = FlagValueSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                product = Product.objects.get(id=data['product_id'])
                attribute = Attribute.objects.get(id=data['attribute_id'])
                batch_item = BatchItem.objects.get(id=data['batch_item_id'])
                
                flag, created = MissingValueFlag.objects.get_or_create(
                    product=product,
                    attribute=attribute,
                    annotator=request.user,
                    batch_item=batch_item,
                    defaults={
                        'requested_value': data['requested_value'],
                        'reason': data.get('reason', ''),
                        'status': 'pending'
                    }
                )
                
                if not created:
                    flag.requested_value = data['requested_value']
                    flag.reason = data.get('reason', '')
                    flag.status = 'pending'
                    flag.save()
                
                return Response({
                    "message": "Value flagged successfully. Admin will review and add it to the database.",
                    "flag_id": flag.id
                })
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def pending(self, request):
        """Get all pending flags for admin review"""
        flags = MissingValueFlag.objects.filter(status='pending')
        serializer = self.get_serializer(flags, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def resolve(self, request, pk=None):
        """Resolve a flag - add value to attribute or reject"""
        flag = self.get_object()
        action = request.data.get('action')  # 'approve' or 'reject'
        resolution_note = request.data.get('resolution_note', '')
        
        if action == 'approve':
            # Add the value to the attribute's allowed_values
            attribute = flag.attribute
            if attribute.allowed_values is None:
                attribute.allowed_values = []
            if flag.requested_value not in attribute.allowed_values:
                attribute.allowed_values.append(flag.requested_value)
                attribute.save()
            
            flag.status = 'resolved'
            flag.resolution_note = resolution_note or f"Value '{flag.requested_value}' added to {attribute.name}"
        elif action == 'reject':
            flag.status = 'rejected'
            flag.resolution_note = resolution_note or 'Request rejected'
        else:
            return Response({"error": "action must be 'approve' or 'reject'"}, status=400)
        
        flag.reviewed_by = request.user
        flag.reviewed_at = timezone.now()
        flag.save()
        
        return Response({
            "message": f"Flag {action}d successfully",
            "flag": MissingValueFlagSerializer(flag).data
        })

class AIProcessingViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated & IsAdmin]
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get current AI processing status"""
        from .models import AIProcessingControl
        
        control = AIProcessingControl.get_control()
        ai_running_batches = AnnotationBatch.objects.filter(
            batch_type='ai',
            status='in_progress'
        ).count()
        
        pending_products = Product.objects.filter(status='pending_ai').count()
        ai_running_products = Product.objects.filter(status='ai_running').count()
        ai_done_products = Product.objects.filter(status='ai_done').count()
        
        return Response({
            'active_batches': ai_running_batches,
            'pending_products': pending_products,
            'processing_products': ai_running_products,
            'completed_products': ai_done_products,
            'is_processing': ai_running_batches > 0 and not control.is_paused,
            'is_paused': control.is_paused,
            'paused_at': control.paused_at.isoformat() if control.paused_at else None
        })

class AIProviderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing AI providers (admin only)"""
    queryset = AIProvider.objects.all()
    serializer_class = AIProviderSerializer
    permission_classes = [permissions.IsAuthenticated & IsAdmin]
    
    def get_serializer_context(self):
        """Add request to serializer context for API key handling"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        """Create AI provider with proper config handling"""
        serializer.save()
    
    def perform_update(self, serializer):
        """Update AI provider with proper config handling"""
        serializer.save()