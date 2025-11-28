"""
Management command to run automated AI processing
Place this file in: products/management/commands/run_ai_processing.py
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Product, AnnotationBatch, BatchItem, Attribute, AIProvider, AISuggestion, AIConsensus
import random
import time

class Command(BaseCommand):
    help = 'Run automated AI processing for all pending products'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of products per batch (10 or 20)'
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously until all products are processed'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        continuous = options['continuous']
        
        allowed_sizes = [10, 15, 20, 25, 30]
        if batch_size not in allowed_sizes:
            self.stdout.write(self.style.ERROR(f'Batch size must be one of {allowed_sizes}'))
            return
        
        if continuous:
            self.stdout.write(self.style.SUCCESS('Starting continuous AI processing...'))
            self.process_all_batches(batch_size)
        else:
            self.stdout.write(self.style.SUCCESS('Processing single batch...'))
            self.process_single_batch(batch_size)
    
    def process_single_batch(self, batch_size):
        """Process a single batch of products"""
        pending_products = list(Product.objects.filter(status='pending_ai')[:batch_size])
        
        if not pending_products:
            self.stdout.write(self.style.WARNING('No pending products found'))
            return
        
        # Create batch
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
        
        self.stdout.write(self.style.SUCCESS(f'Created batch {batch.id} with {len(pending_products)} products'))
        
        # Process the batch
        self.process_batch(batch, pending_products)
    
    def process_all_batches(self, batch_size):
        """Process all pending products in batches"""
        batch_count = 0
        
        while True:
            pending_products = list(Product.objects.filter(status='pending_ai')[:batch_size])
            
            if not pending_products:
                self.stdout.write(self.style.SUCCESS(f'All products processed! Total batches: {batch_count}'))
                break
            
            batch_count += 1
            
            # Create batch
            batch = AnnotationBatch.objects.create(
                name=f"AI Batch {batch_count} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                batch_type='ai',
                status='in_progress',
                batch_size=len(pending_products)
            )
            
            product_ids = [product.id for product in pending_products]
            
            for product in pending_products:
                BatchItem.objects.create(batch=batch, product=product)
            
            Product.objects.filter(id__in=product_ids).update(status='ai_running')
            
            self.stdout.write(self.style.SUCCESS(f'Processing batch {batch_count} with {len(pending_products)} products'))
            
            # Process the batch
            self.process_batch(batch, pending_products)
            
            # Small delay between batches
            time.sleep(1)
    
    def process_batch(self, batch, products):
        """Process a batch of products with AI"""
        ai_providers = list(AIProvider.objects.filter(is_active=True))
        
        if not ai_providers:
            self.stdout.write(self.style.ERROR('No active AI providers found'))
            batch.status = 'completed'
            batch.save()
            return
        
        for index, product in enumerate(products):
            self.stdout.write(f'  Processing product {index+1}/{len(products)}: {product.name}')
            
            # Simulate processing time
            time.sleep(2)
            
            applicable_attributes = list(product.get_applicable_attributes())
            if not applicable_attributes:
                continue
            
            for attribute in applicable_attributes:
                # Get suggestions from each provider
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
                    AIConsensus.record(
                        product=product,
                        attribute=attribute,
                        consensus_value=consensus_value,
                        method='weighted_majority',
                        confidence=round(random.uniform(0.8, 0.98), 4)
                    )
            
            # Update product status
            product.status = 'ai_done'
            product.save()
            
            # Update batch progress
            progress = ((index + 1) / len(products)) * 100
            batch.progress = progress
            batch.save()
            
            self.stdout.write(f'    Completed {index+1}/{len(products)} - Progress: {progress:.1f}%')
        
        # Mark batch as completed
        batch.status = 'completed'
        batch.progress = 100
        batch.save()
        
        self.stdout.write(self.style.SUCCESS(f'Batch {batch.id} completed successfully'))
    
    def generate_ai_suggestion(self, product, attribute, provider):
        """Generate AI suggestions - replace with actual AI API calls"""
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
        """Build consensus from multiple AI suggestions"""
        if not suggestions:
            return ""
        
        value_counts = {}
        for suggestion in suggestions:
            value = suggestion.suggested_value
            confidence = float(suggestion.confidence_score)
            value_counts[value] = value_counts.get(value, 0) + confidence
        
        return max(value_counts.items(), key=lambda x: x[1])[0]