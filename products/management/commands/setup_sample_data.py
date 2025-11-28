from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from products.models import (
    Product,
    Attribute,
    Category,
    SubCategory,
    CategoryAttributeMapping,
)

class Command(BaseCommand):
    help = 'Setup sample data for testing with 100 products'

    def handle(self, *args, **options):
        category_cache = {}
        subcategory_cache = {}

        def normalize(value):
            if not value:
                return None
            value = value.strip()
            return value or None

        def get_category(name):
            name = normalize(name)
            if not name:
                return None
            if name not in category_cache:
                category_cache[name], _ = Category.objects.get_or_create(name=name)
            return category_cache[name]

        def get_subcategory(category, name):
            name = normalize(name)
            if not category or not name:
                return None
            cache_key = (category.id, name)
            if cache_key not in subcategory_cache:
                subcategory_cache[cache_key], _ = SubCategory.objects.get_or_create(
                    category=category,
                    name=name
                )
            return subcategory_cache[cache_key]
        
        # Create groups
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        annotator_group, _ = Group.objects.get_or_create(name='Annotator')
        
        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True}
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            admin_user.groups.add(admin_group)
            self.stdout.write(self.style.SUCCESS('Created admin user'))
        
        # Create annotator users
        annotators_data = [
            {'username': 'annotator1', 'email': 'annotator1@example.com'},
            {'username': 'annotator2', 'email': 'annotator2@example.com'},
            {'username': 'annotator3', 'email': 'annotator3@example.com'},
        ]
        
        for annotator_data in annotators_data:
            annotator_user, created = User.objects.get_or_create(
                username=annotator_data['username'],
                defaults=annotator_data
            )
            if created:
                annotator_user.set_password('annotator123')
                annotator_user.save()
                annotator_user.groups.add(annotator_group)
                self.stdout.write(self.style.SUCCESS(f'Created annotator user: {annotator_user.username}'))
        
        # Create sample attributes
        attributes_data = [
            {'name': 'Color', 'data_type': 'enum', 'allowed_values': ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow', 'Pink', 'Purple', 'Orange', 'Brown', 'Gray', 'Navy', 'Maroon', 'Teal', 'Cyan', 'Magenta', 'Lavender', 'Peach', 'Mint', 'Beige']},
            {'name': 'Size', 'data_type': 'enum', 'allowed_values': ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', '4XL', '5XL']},
            {'name': 'Material', 'data_type': 'enum', 'allowed_values': ['Cotton', 'Polyester', 'Silk', 'Wool', 'Linen', 'Denim', 'Leather', 'Suede', 'Cashmere', 'Velvet', 'Spandex', 'Nylon', 'Rayon', 'Chiffon', 'Satin', 'Fleece', 'Corduroy', 'Tweed', 'Jersey', 'Organza']},
            {'name': 'Sleeve Length', 'data_type': 'enum', 'allowed_values': ['Short', 'Long', 'Sleeveless', 'Three-Quarter', 'Cap Sleeve', 'Puff Sleeve', 'Bell Sleeve', 'Flutter Sleeve']},
            {'name': 'Neckline', 'data_type': 'enum', 'allowed_values': ['Round', 'V-Neck', 'Collar', 'Boat Neck', 'Square', 'Sweetheart', 'Halter', 'Off-Shoulder', 'Crew Neck', 'Scoop Neck']},
            {'name': 'Fit', 'data_type': 'enum', 'allowed_values': ['Slim', 'Regular', 'Loose', 'Oversized', 'Skinny', 'Relaxed', 'Tailored', 'Athletic', 'Boyfriend', 'A-Line']},
            {'name': 'Season', 'data_type': 'enum', 'allowed_values': ['Spring', 'Summer', 'Fall', 'Winter', 'All Season', 'Resort', 'Holiday']},
            {'name': 'Pattern', 'data_type': 'enum', 'allowed_values': ['Solid', 'Striped', 'Printed', 'Floral', 'Checkered', 'Plaid', 'Polka Dot', 'Animal Print', 'Geometric', 'Abstract', 'Paisley', 'Tie-Dye', 'Camouflage', 'Houndstooth', 'Herringbone']},
            {'name': 'Occasion', 'data_type': 'enum', 'allowed_values': ['Casual', 'Formal', 'Business', 'Sports', 'Beach', 'Party', 'Wedding', 'Evening', 'Vacation', 'Everyday']},
            {'name': 'Care Instructions', 'data_type': 'enum', 'allowed_values': ['Machine Wash', 'Hand Wash', 'Dry Clean Only', 'Tumble Dry', 'Line Dry', 'Do Not Bleach', 'Iron Low Heat']},
            {'name': 'Shoe Size', 'data_type': 'enum', 'allowed_values': ['5', '5.5', '6', '6.5', '7', '7.5', '8', '8.5', '9', '9.5', '10', '10.5', '11', '11.5', '12', '12.5', '13', '14']},
            {'name': 'Heel Height', 'data_type': 'enum', 'allowed_values': ['Flat', '1 inch', '2 inches', '3 inches', '4 inches', '5+ inches']},
            {'name': 'Closure Type', 'data_type': 'enum', 'allowed_values': ['Slip-On', 'Lace-Up', 'Buckle', 'Velcro', 'Zipper', 'Button', 'Hook-and-Loop']},
            {'name': 'Strap Style', 'data_type': 'enum', 'allowed_values': ['Crossbody', 'Shoulder', 'Top Handle', 'Backpack', 'Clutch', 'Wristlet', 'Messenger']},
            {'name': 'Metal Type', 'data_type': 'enum', 'allowed_values': ['Gold', 'White Gold', 'Rose Gold', 'Silver', 'Platinum', 'Stainless Steel', 'Titanium']},
            {'name': 'Stone Type', 'data_type': 'enum', 'allowed_values': ['Diamond', 'Cubic Zirconia', 'Sapphire', 'Emerald', 'Ruby', 'Pearl', 'Amethyst', 'Topaz', 'Opal']},
            {'name': 'Frame Shape', 'data_type': 'enum', 'allowed_values': ['Aviator', 'Round', 'Cat Eye', 'Square', 'Rectangle', 'Wayfarer', 'Oversized']},
        ]
        
        for attr_data in attributes_data:
            attribute, created = Attribute.objects.get_or_create(
                name=attr_data['name'],
                defaults=attr_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created attribute: {attribute.name}'))

        # Map attributes to categories/subcategories
        attribute_lookup = {attr.name: attr for attr in Attribute.objects.all()}
        category_attribute_map = {
            ('Clothing', None): ['Color', 'Size', 'Material', 'Fit', 'Pattern', 'Season', 'Occasion', 'Care Instructions'],
            ('Clothing', 'T-Shirts'): ['Sleeve Length', 'Neckline'],
            ('Clothing', 'Dresses'): ['Sleeve Length', 'Neckline'],
            ('Clothing', 'Sweaters'): ['Sleeve Length', 'Neckline'],
            ('Clothing', 'Hoodies'): ['Sleeve Length'],
            ('Clothing', 'Jackets'): ['Sleeve Length'],
            ('Clothing', 'Coats'): ['Sleeve Length'],
            ('Clothing', 'Blouses'): ['Sleeve Length', 'Neckline'],
            ('Footwear', None): ['Color', 'Material', 'Pattern', 'Season', 'Occasion', 'Care Instructions', 'Closure Type', 'Shoe Size', 'Heel Height'],
            ('Footwear', 'Sneakers'): ['Closure Type', 'Shoe Size'],
            ('Footwear', 'Boots'): ['Closure Type', 'Heel Height'],
            ('Footwear', 'Heels'): ['Heel Height', 'Closure Type'],
            ('Accessories', None): ['Color', 'Material', 'Pattern', 'Occasion'],
            ('Accessories', 'Bags'): ['Strap Style', 'Closure Type'],
            ('Accessories', 'Jewelry'): ['Metal Type', 'Stone Type'],
            ('Accessories', 'Watches'): ['Strap Style', 'Closure Type', 'Metal Type'],
            ('Accessories', 'Hats'): ['Size'],
            ('Accessories', 'Belts'): ['Size'],
            ('Accessories', 'Gloves'): ['Size', 'Material'],
            ('Accessories', 'Sunglasses'): ['Frame Shape', 'Material'],
        }

        created_mappings = 0
        for (category_name, subcategory_name), attr_names in category_attribute_map.items():
            category_obj = get_category(category_name)
            subcategory_obj = get_subcategory(category_obj, subcategory_name)
            for attr_name in attr_names:
                attribute = attribute_lookup.get(attr_name)
                if not attribute:
                    continue
                _, created = CategoryAttributeMapping.objects.get_or_create(
                    category=category_obj,
                    subcategory=subcategory_obj,
                    attribute=attribute,
                    defaults={'is_required': True}
                )
                if created:
                    created_mappings += 1
        if created_mappings:
            self.stdout.write(self.style.SUCCESS(f'Created {created_mappings} category-attribute mappings'))
        
        # Create 100 sample products with Unsplash images
        products_data = [
            # Clothing - T-Shirts (10)
            {
                'external_sku': 'TSHIRT001',
                'name': 'Basic Cotton T-Shirt',
                'description': 'Comfortable basic cotton t-shirt for everyday wear',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': [
                    'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500&h=500&fit=crop',
                    'https://images.unsplash.com/photo-1586790170083-2f9ceadc732d?w=500&h=500&fit=crop'
                ],
                'price': 19.99
            },
            {
                'external_sku': 'TSHIRT002',
                'name': 'Premium V-Neck T-Shirt',
                'description': 'Soft premium cotton v-neck t-shirt',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&h=500&fit=crop'],
                'price': 24.99
            },
            {
                'external_sku': 'TSHIRT003',
                'name': 'Graphic Print T-Shirt',
                'description': 'Cotton t-shirt with artistic graphic print',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1503341455253-b2e723bb3dbb?w=500&h=500&fit=crop'],
                'price': 29.99
            },
            {
                'external_sku': 'TSHIRT004',
                'name': 'Organic Cotton T-Shirt',
                'description': 'Eco-friendly organic cotton t-shirt',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=500&h=500&fit=crop'],
                'price': 27.99
            },
            {
                'external_sku': 'TSHIRT005',
                'name': 'Striped Crew Neck T-Shirt',
                'description': 'Classic striped crew neck t-shirt',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=500&h=500&fit=crop'],
                'price': 22.99
            },
            {
                'external_sku': 'TSHIRT006',
                'name': 'Performance Athletic T-Shirt',
                'description': 'Moisture-wicking athletic t-shirt for sports',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=500&h=500&fit=crop'],
                'price': 34.99
            },
            {
                'external_sku': 'TSHIRT007',
                'name': 'Oversized Comfort T-Shirt',
                'description': 'Soft oversized t-shirt for ultimate comfort',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=500&h=500&fit=crop'],
                'price': 26.99
            },
            {
                'external_sku': 'TSHIRT008',
                'name': 'Long Sleeve Basic T-Shirt',
                'description': 'Comfortable long sleeve cotton t-shirt',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=500&h=500&fit=crop'],
                'price': 32.99
            },
            {
                'external_sku': 'TSHIRT009',
                'name': 'Pocket T-Shirt',
                'description': 'Classic t-shirt with chest pocket',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=500&h=500&fit=crop'],
                'price': 23.99
            },
            {
                'external_sku': 'TSHIRT010',
                'name': 'Ringer T-Shirt Vintage',
                'description': 'Vintage style ringer t-shirt with contrast trim',
                'category': 'Clothing',
                'subcategory': 'T-Shirts',
                'image_urls': ['https://images.unsplash.com/photo-1586363104862-3a5e2ab60d99?w=500&h=500&fit=crop'],
                'price': 28.99
            },
            
            # Clothing - Dresses (10)
            {
                'external_sku': 'DRESS001',
                'name': 'Summer Floral Dress',
                'description': 'Beautiful floral dress perfect for summer occasions',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=500&h=500&fit=crop'],
                'price': 49.99
            },
            {
                'external_sku': 'DRESS002',
                'name': 'Elegant Cocktail Dress',
                'description': 'Sophisticated cocktail dress for evening events',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'DRESS003',
                'name': 'Maxi Summer Dress',
                'description': 'Flowy maxi dress perfect for warm weather',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=500&h=500&fit=crop'],
                'price': 59.99
            },
            {
                'external_sku': 'DRESS004',
                'name': 'Bodycon Party Dress',
                'description': 'Form-fitting bodycon dress for parties',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1539008835657-9e8e9680c956?w=500&h=500&fit=crop'],
                'price': 69.99
            },
            {
                'external_sku': 'DRESS005',
                'name': 'A-Line Casual Dress',
                'description': 'Comfortable A-line dress for everyday wear',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1583496661160-fb5886a13d77?w=500&h=500&fit=crop'],
                'price': 45.99
            },
            {
                'external_sku': 'DRESS006',
                'name': 'Wrap Midi Dress',
                'description': 'Flattering wrap midi dress with belt',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'DRESS007',
                'name': 'Off-Shoulder Summer Dress',
                'description': 'Chic off-shoulder dress for summer outings',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1581044777550-4cfa60707c03?w=500&h=500&fit=crop'],
                'price': 65.99
            },
            {
                'external_sku': 'DRESS008',
                'name': 'Business Formal Dress',
                'description': 'Professional dress for office and meetings',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1445205170230-053b83016050?w=500&h=500&fit=crop'],
                'price': 99.99
            },
            {
                'external_sku': 'DRESS009',
                'name': 'Bohemian Maxi Dress',
                'description': 'Bohemian style maxi dress with embroidery',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=500&h=500&fit=crop'],
                'price': 85.99
            },
            {
                'external_sku': 'DRESS010',
                'name': 'Little Black Dress',
                'description': 'Classic little black dress for all occasions',
                'category': 'Clothing',
                'subcategory': 'Dresses',
                'image_urls': ['https://images.unsplash.com/photo-1539008835657-9e8e9680c956?w=500&h=500&fit=crop'],
                'price': 74.99
            },
            
            # Clothing - Jeans (10)
            {
                'external_sku': 'JEANS001',
                'name': 'Slim Fit Jeans',
                'description': 'Comfortable slim fit jeans made from premium denim',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': [
                    'https://images.unsplash.com/photo-1542272604-787c3835535d?w=500&h=500&fit=crop',
                    'https://images.unsplash.com/photo-1582418702059-97ebafb35d09?w=500&h=500&fit=crop'
                ],
                'price': 59.99
            },
            {
                'external_sku': 'JEANS002',
                'name': 'Skinny Jeans',
                'description': 'Form-fitting skinny jeans with stretch',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500&h=500&fit=crop'],
                'price': 64.99
            },
            {
                'external_sku': 'JEANS003',
                'name': 'Relaxed Fit Jeans',
                'description': 'Comfortable relaxed fit jeans for all-day wear',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=500&h=500&fit=crop'],
                'price': 54.99
            },
            {
                'external_sku': 'JEANS004',
                'name': 'Bootcut Jeans',
                'description': 'Classic bootcut jeans perfect with boots',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=500&h=500&fit=crop'],
                'price': 59.99
            },
            {
                'external_sku': 'JEANS005',
                'name': 'High-Waisted Jeans',
                'description': 'Flattering high-waisted jeans with vintage wash',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1582418702059-97ebafb35d09?w=500&h=500&fit=crop'],
                'price': 69.99
            },
            {
                'external_sku': 'JEANS006',
                'name': 'Distressed Denim Jeans',
                'description': 'Fashionable distressed jeans with ripped details',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500&h=500&fit=crop'],
                'price': 74.99
            },
            {
                'external_sku': 'JEANS007',
                'name': 'Black Denim Jeans',
                'description': 'Versatile black jeans for various occasions',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=500&h=500&fit=crop'],
                'price': 62.99
            },
            {
                'external_sku': 'JEANS008',
                'name': 'Boyfriend Jeans',
                'description': 'Comfortable boyfriend fit jeans with casual style',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=500&h=500&fit=crop'],
                'price': 57.99
            },
            {
                'external_sku': 'JEANS009',
                'name': 'Raw Denim Jeans',
                'description': 'Premium raw denim that molds to your body',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1582418702059-97ebafb35d09?w=500&h=500&fit=crop'],
                'price': 119.99
            },
            {
                'external_sku': 'JEANS010',
                'name': 'Stretch Skinny Jeans',
                'description': 'Super stretch skinny jeans for maximum comfort',
                'category': 'Clothing',
                'subcategory': 'Jeans',
                'image_urls': ['https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500&h=500&fit=crop'],
                'price': 67.99
            },
            
            # Clothing - Jackets & Outerwear (10)
            {
                'external_sku': 'JACKET001',
                'name': 'Denim Jacket',
                'description': 'Classic denim jacket for casual wear',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'JACKET002',
                'name': 'Leather Moto Jacket',
                'description': 'Stylish leather motorcycle jacket',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 199.99
            },
            {
                'external_sku': 'JACKET003',
                'name': 'Bomber Jacket',
                'description': 'Classic bomber jacket with ribbed cuffs',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'JACKET004',
                'name': 'Rain Jacket',
                'description': 'Waterproof rain jacket for outdoor activities',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 69.99
            },
            {
                'external_sku': 'JACKET005',
                'name': 'Quilted Puffer Jacket',
                'description': 'Warm quilted puffer jacket for winter',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=500&h=500&fit=crop'],
                'price': 129.99
            },
            {
                'external_sku': 'JACKET006',
                'name': 'Blazer',
                'description': 'Professional blazer for business occasions',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 149.99
            },
            {
                'external_sku': 'JACKET007',
                'name': 'Windbreaker',
                'description': 'Lightweight windbreaker for active wear',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=500&h=500&fit=crop'],
                'price': 59.99
            },
            {
                'external_sku': 'JACKET008',
                'name': 'Field Jacket',
                'description': 'Utility field jacket with multiple pockets',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 99.99
            },
            {
                'external_sku': 'JACKET009',
                'name': 'Fleece Jacket',
                'description': 'Soft fleece jacket for casual comfort',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'JACKET010',
                'name': 'Trench Coat',
                'description': 'Classic trench coat for rainy days',
                'category': 'Clothing',
                'subcategory': 'Jackets',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 179.99
            },
            
            # Footwear (10)
            {
                'external_sku': 'SHOES001',
                'name': 'Running Shoes',
                'description': 'Comfortable running shoes for sports',
                'category': 'Footwear',
                'subcategory': 'Sneakers',
                'image_urls': [
                    'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop',
                    'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=500&h=500&fit=crop'
                ],
                'price': 129.99
            },
            {
                'external_sku': 'SHOES002',
                'name': 'Leather Boots',
                'description': 'Durable leather boots for outdoor wear',
                'category': 'Footwear',
                'subcategory': 'Boots',
                'image_urls': ['https://images.unsplash.com/photo-1542280756-74b2f55e73ab?w=500&h=500&fit=crop'],
                'price': 159.99
            },
            {
                'external_sku': 'SHOES003',
                'name': 'Casual Loafers',
                'description': 'Comfortable loafers for casual occasions',
                'category': 'Footwear',
                'subcategory': 'Loafers',
                'image_urls': ['https://images.unsplash.com/photo-1560769684-55015cee73d8?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'SHOES004',
                'name': 'High Heels',
                'description': 'Elegant high heels for formal events',
                'category': 'Footwear',
                'subcategory': 'Heels',
                'image_urls': ['https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=500&h=500&fit=crop'],
                'price': 119.99
            },
            {
                'external_sku': 'SHOES005',
                'name': 'Sandals',
                'description': 'Comfortable sandals for summer wear',
                'category': 'Footwear',
                'subcategory': 'Sandals',
                'image_urls': ['https://images.unsplash.com/photo-1563241527-3004b7be0ffd?w=500&h=500&fit=crop'],
                'price': 49.99
            },
            {
                'external_sku': 'SHOES006',
                'name': 'Basketball Shoes',
                'description': 'High-performance basketball shoes',
                'category': 'Footwear',
                'subcategory': 'Sneakers',
                'image_urls': ['https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=500&h=500&fit=crop'],
                'price': 139.99
            },
            {
                'external_sku': 'SHOES007',
                'name': 'Oxford Shoes',
                'description': 'Classic oxford shoes for business wear',
                'category': 'Footwear',
                'subcategory': 'Dress Shoes',
                'image_urls': ['https://images.unsplash.com/photo-1560769684-55015cee73d8?w=500&h=500&fit=crop'],
                'price': 149.99
            },
            {
                'external_sku': 'SHOES008',
                'name': 'Slip-on Sneakers',
                'description': 'Convenient slip-on sneakers for casual wear',
                'category': 'Footwear',
                'subcategory': 'Sneakers',
                'image_urls': ['https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'SHOES009',
                'name': 'Hiking Boots',
                'description': 'Durable hiking boots for outdoor adventures',
                'category': 'Footwear',
                'subcategory': 'Boots',
                'image_urls': ['https://images.unsplash.com/photo-1542280756-74b2f55e73ab?w=500&h=500&fit=crop'],
                'price': 179.99
            },
            {
                'external_sku': 'SHOES010',
                'name': 'Flip Flops',
                'description': 'Comfortable flip flops for beach and pool',
                'category': 'Footwear',
                'subcategory': 'Sandals',
                'image_urls': ['https://images.unsplash.com/photo-1563241527-3004b7be0ffd?w=500&h=500&fit=crop'],
                'price': 24.99
            },
            
            # Accessories - Bags (10)
            {
                'external_sku': 'BAG001',
                'name': 'Leather Handbag',
                'description': 'Genuine leather handbag for women',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=500&h=500&fit=crop'],
                'price': 199.99
            },
            {
                'external_sku': 'BAG002',
                'name': 'Backpack',
                'description': 'Durable backpack for daily use',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'BAG003',
                'name': 'Crossbody Bag',
                'description': 'Convenient crossbody bag for hands-free carrying',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=500&h=500&fit=crop'],
                'price': 129.99
            },
            {
                'external_sku': 'BAG004',
                'name': 'Tote Bag',
                'description': 'Spacious tote bag for shopping and beach',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop'],
                'price': 59.99
            },
            {
                'external_sku': 'BAG005',
                'name': 'Clutch',
                'description': 'Elegant clutch for evening events',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'BAG006',
                'name': 'Messenger Bag',
                'description': 'Stylish messenger bag for work and school',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop'],
                'price': 109.99
            },
            {
                'external_sku': 'BAG007',
                'name': 'Travel Duffel',
                'description': 'Spacious duffel bag for travel and gym',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=500&h=500&fit=crop'],
                'price': 139.99
            },
            {
                'external_sku': 'BAG008',
                'name': 'Laptop Bag',
                'description': 'Protective laptop bag with padding',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop'],
                'price': 99.99
            },
            {
                'external_sku': 'BAG009',
                'name': 'Waist Bag',
                'description': 'Convenient waist bag for active lifestyle',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=500&h=500&fit=crop'],
                'price': 49.99
            },
            {
                'external_sku': 'BAG010',
                'name': 'Beach Bag',
                'description': 'Large beach bag with waterproof lining',
                'category': 'Accessories',
                'subcategory': 'Bags',
                'image_urls': ['https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop'],
                'price': 39.99
            },
            
            # Accessories - Hats & Headwear (10)
            {
                'external_sku': 'HAT001',
                'name': 'Baseball Cap',
                'description': 'Casual baseball cap for sun protection',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1521369909029-2afed882baee?w=500&h=500&fit=crop'],
                'price': 24.99
            },
            {
                'external_sku': 'HAT002',
                'name': 'Beanie',
                'description': 'Warm beanie for cold weather',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1576871337632-b9aef4c17ab9?w=500&h=500&fit=crop'],
                'price': 19.99
            },
            {
                'external_sku': 'HAT003',
                'name': 'Fedora',
                'description': 'Stylish fedora hat for formal occasions',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1534215754734-18e55d13e346?w=500&h=500&fit=crop'],
                'price': 49.99
            },
            {
                'external_sku': 'HAT004',
                'name': 'Sun Hat',
                'description': 'Wide-brim sun hat for beach and outdoor',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1521369909029-2afed882baee?w=500&h=500&fit=crop'],
                'price': 34.99
            },
            {
                'external_sku': 'HAT005',
                'name': 'Bucket Hat',
                'description': 'Trendy bucket hat for casual style',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1576871337632-b9aef4c17ab9?w=500&h=500&fit=crop'],
                'price': 29.99
            },
            {
                'external_sku': 'HAT006',
                'name': 'Beret',
                'description': 'Classic beret for artistic style',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1534215754734-18e55d13e346?w=500&h=500&fit=crop'],
                'price': 27.99
            },
            {
                'external_sku': 'HAT007',
                'name': 'Visor',
                'description': 'Sports visor for outdoor activities',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1521369909029-2afed882baee?w=500&h=500&fit=crop'],
                'price': 22.99
            },
            {
                'external_sku': 'HAT008',
                'name': 'Newsboy Cap',
                'description': 'Vintage newsboy cap for retro style',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1576871337632-b9aef4c17ab9?w=500&h=500&fit=crop'],
                'price': 39.99
            },
            {
                'external_sku': 'HAT009',
                'name': 'Trapper Hat',
                'description': 'Warm trapper hat with ear flaps',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1534215754734-18e55d13e346?w=500&h=500&fit=crop'],
                'price': 44.99
            },
            {
                'external_sku': 'HAT010',
                'name': 'Panama Hat',
                'description': 'Lightweight panama hat for summer',
                'category': 'Accessories',
                'subcategory': 'Hats',
                'image_urls': ['https://images.unsplash.com/photo-1521369909029-2afed882baee?w=500&h=500&fit=crop'],
                'price': 59.99
            },
            
            # Accessories - Jewelry & Watches (10)
            {
                'external_sku': 'JEWELRY001',
                'name': 'Silver Necklace',
                'description': 'Elegant silver necklace with pendant',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=500&h=500&fit=crop'],
                'price': 129.99
            },
            {
                'external_sku': 'JEWELRY002',
                'name': 'Gold Bracelet',
                'description': 'Beautiful gold bracelet with charm',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=500&h=500&fit=crop'],
                'price': 199.99
            },
            {
                'external_sku': 'JEWELRY003',
                'name': 'Diamond Earrings',
                'description': 'Sparkling diamond stud earrings',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=500&h=500&fit=crop'],
                'price': 299.99
            },
            {
                'external_sku': 'JEWELRY004',
                'name': 'Pearl Necklace',
                'description': 'Classic pearl necklace for formal wear',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=500&h=500&fit=crop'],
                'price': 249.99
            },
            {
                'external_sku': 'JEWELRY005',
                'name': 'Rose Gold Ring',
                'description': 'Elegant rose gold ring with stone',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=500&h=500&fit=crop'],
                'price': 179.99
            },
            {
                'external_sku': 'JEWELRY006',
                'name': 'Leather Watch',
                'description': 'Classic leather strap watch',
                'category': 'Accessories',
                'subcategory': 'Watches',
                'image_urls': ['https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop'],
                'price': 149.99
            },
            {
                'external_sku': 'JEWELRY007',
                'name': 'Smart Watch',
                'description': 'Advanced smart watch with fitness tracking',
                'category': 'Accessories',
                'subcategory': 'Watches',
                'image_urls': ['https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop'],
                'price': 249.99
            },
            {
                'external_sku': 'JEWELRY008',
                'name': 'Charm Bracelet',
                'description': 'Silver charm bracelet with multiple charms',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'JEWELRY009',
                'name': 'Anklet',
                'description': 'Delicate gold anklet for summer',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=500&h=500&fit=crop'],
                'price': 69.99
            },
            {
                'external_sku': 'JEWELRY010',
                'name': 'Cuff Links',
                'description': 'Elegant cuff links for formal shirts',
                'category': 'Accessories',
                'subcategory': 'Jewelry',
                'image_urls': ['https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=500&h=500&fit=crop'],
                'price': 59.99
            },
            
            # Accessories - Scarves & Belts (10)
            {
                'external_sku': 'SCARF001',
                'name': 'Silk Scarf',
                'description': 'Luxurious silk scarf with printed pattern',
                'category': 'Accessories',
                'subcategory': 'Scarves',
                'image_urls': ['https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop'],
                'price': 45.99
            },
            {
                'external_sku': 'SCARF002',
                'name': 'Cashmere Scarf',
                'description': 'Warm cashmere scarf for winter',
                'category': 'Accessories',
                'subcategory': 'Scarves',
                'image_urls': ['https://images.unsplash.com/photo-1574180045827-681f8a1a9622?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'SCARF003',
                'name': 'Infinity Scarf',
                'description': 'Versatile infinity scarf in various colors',
                'category': 'Accessories',
                'subcategory': 'Scarves',
                'image_urls': ['https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop'],
                'price': 39.99
            },
            {
                'external_sku': 'SCARF004',
                'name': 'Pashmina Shawl',
                'description': 'Large pashmina shawl for evening wear',
                'category': 'Accessories',
                'subcategory': 'Scarves',
                'image_urls': ['https://images.unsplash.com/photo-1574180045827-681f8a1a9622?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'SCARF005',
                'name': 'Lightweight Scarf',
                'description': 'Lightweight scarf for spring and fall',
                'category': 'Accessories',
                'subcategory': 'Scarves',
                'image_urls': ['https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop'],
                'price': 34.99
            },
            {
                'external_sku': 'BELT001',
                'name': 'Leather Belt',
                'description': 'Genuine leather belt for men',
                'category': 'Accessories',
                'subcategory': 'Belts',
                'image_urls': ['https://images.unsplash.com/photo-1601924994987-69e26d50dc96?w=500&h=500&fit=crop'],
                'price': 34.99
            },
            {
                'external_sku': 'BELT002',
                'name': 'Designer Belt',
                'description': 'Fashion designer belt with signature buckle',
                'category': 'Accessories',
                'subcategory': 'Belts',
                'image_urls': ['https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop'],
                'price': 99.99
            },
            {
                'external_sku': 'BELT003',
                'name': 'Webbing Belt',
                'description': 'Casual webbing belt for everyday wear',
                'category': 'Accessories',
                'subcategory': 'Belts',
                'image_urls': ['https://images.unsplash.com/photo-1601924994987-69e26d50dc96?w=500&h=500&fit=crop'],
                'price': 24.99
            },
            {
                'external_sku': 'BELT004',
                'name': 'Western Belt',
                'description': 'Western style belt with decorative buckle',
                'category': 'Accessories',
                'subcategory': 'Belts',
                'image_urls': ['https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop'],
                'price': 49.99
            },
            {
                'external_sku': 'BELT005',
                'name': 'Reversible Belt',
                'description': 'Versatile reversible belt with two colors',
                'category': 'Accessories',
                'subcategory': 'Belts',
                'image_urls': ['https://images.unsplash.com/photo-1601924994987-69e26d50dc96?w=500&h=500&fit=crop'],
                'price': 44.99
            },
            
            # Other Categories (10)
            {
                'external_sku': 'SOCKS001',
                'name': 'Cotton Socks',
                'description': 'Comfortable cotton socks pack of 3',
                'category': 'Clothing',
                'subcategory': 'Socks',
                'image_urls': ['https://images.unsplash.com/photo-1586359830987-6cf84813d0a5?w=500&h=500&fit=crop'],
                'price': 14.99
            },
            {
                'external_sku': 'GLOVES001',
                'name': 'Winter Gloves',
                'description': 'Warm winter gloves with touch screen compatibility',
                'category': 'Accessories',
                'subcategory': 'Gloves',
                'image_urls': ['https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=500&h=500&fit=crop'],
                'price': 29.99
            },
            {
                'external_sku': 'SUNGLASS001',
                'name': 'Aviator Sunglasses',
                'description': 'Classic aviator sunglasses with UV protection',
                'category': 'Accessories',
                'subcategory': 'Sunglasses',
                'image_urls': ['https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'SWEATER001',
                'name': 'Wool Sweater',
                'description': 'Warm wool sweater for winter season',
                'category': 'Clothing',
                'subcategory': 'Sweaters',
                'image_urls': ['https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=500&h=500&fit=crop'],
                'price': 89.99
            },
            {
                'external_sku': 'SKIRT001',
                'name': 'A-Line Skirt',
                'description': 'Elegant A-line skirt for office wear',
                'category': 'Clothing',
                'subcategory': 'Skirts',
                'image_urls': ['https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=500&h=500&fit=crop'],
                'price': 39.99
            },
            {
                'external_sku': 'HOODIE001',
                'name': 'Zip Hoodie',
                'description': 'Comfortable zip-up hoodie for casual wear',
                'category': 'Clothing',
                'subcategory': 'Hoodies',
                'image_urls': ['https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=500&h=500&fit=crop'],
                'price': 49.99
            },
            {
                'external_sku': 'SHORTS001',
                'name': 'Sports Shorts',
                'description': 'Lightweight sports shorts for workouts',
                'category': 'Clothing',
                'subcategory': 'Shorts',
                'image_urls': ['https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=500&h=500&fit=crop'],
                'price': 34.99
            },
            {
                'external_sku': 'BLOUSE001',
                'name': 'Silk Blouse',
                'description': 'Elegant silk blouse for formal occasions',
                'category': 'Clothing',
                'subcategory': 'Blouses',
                'image_urls': ['https://images.unsplash.com/photo-1594223274512-ad4803739b7c?w=500&h=500&fit=crop'],
                'price': 79.99
            },
            {
                'external_sku': 'COAT001',
                'name': 'Winter Coat',
                'description': 'Warm winter coat with insulation',
                'category': 'Clothing',
                'subcategory': 'Coats',
                'image_urls': ['https://images.unsplash.com/photo-1551028719-00167b16eac5?w=500&h=500&fit=crop'],
                'price': 199.99
            },
            {
                'external_sku': 'UNDERWEAR001',
                'name': 'Cotton Underwear',
                'description': 'Comfortable cotton underwear pack of 5',
                'category': 'Clothing',
                'subcategory': 'Underwear',
                'image_urls': ['https://images.unsplash.com/photo-1586359830987-6cf84813d0a5?w=500&h=500&fit=crop'],
                'price': 29.99
            }
        ]
        
        for product_data in products_data:
            category_obj = get_category(product_data.get('category'))
            subcategory_obj = get_subcategory(category_obj, product_data.get('subcategory'))
            creation_defaults = {
                **product_data,
                'category': category_obj,
                'subcategory': subcategory_obj,
            }
            product, created = Product.objects.get_or_create(
                external_sku=product_data['external_sku'],
                defaults=creation_defaults
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created product: {product.name}'))
        
        self.stdout.write(self.style.SUCCESS('Sample data setup completed successfully with 100 products!'))