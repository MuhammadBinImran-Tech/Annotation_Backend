from django.db import migrations, models
import django.db.models.deletion


def seed_category_attribute_mappings(apps, schema_editor):
    Attribute = apps.get_model('products', 'Attribute')
    CategoryAttributeMapping = apps.get_model('products', 'CategoryAttributeMapping')

    attribute_lookup = {attr.name: attr for attr in Attribute.objects.all()}
    mapping_data = {
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

    for (category, subcategory), attr_names in mapping_data.items():
        for attr_name in attr_names:
            attribute = attribute_lookup.get(attr_name)
            if not attribute:
                continue
            CategoryAttributeMapping.objects.get_or_create(
                category=category,
                subcategory=subcategory,
                attribute=attribute,
                defaults={'is_required': True}
            )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_delete_categoryattributemapping'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoryAttributeMapping',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('category', models.CharField(max_length=80)),
                ('subcategory', models.CharField(blank=True, max_length=80, null=True)),
                ('is_required', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attribute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_mappings', to='products.attribute')),
            ],
            options={
                'db_table': 'category_attribute_mappings',
                'ordering': ['category', 'subcategory', 'attribute__name'],
                'unique_together': {('category', 'subcategory', 'attribute')},
                'indexes': [models.Index(fields=['category', 'subcategory'], name='category_at_categor_f0ba45_idx')],
            },
        ),
        migrations.RunPython(seed_category_attribute_mappings, migrations.RunPython.noop),
    ]

