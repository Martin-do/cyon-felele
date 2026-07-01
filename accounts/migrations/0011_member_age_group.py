from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_member_is_flyer_locked'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='age_group',
            field=models.CharField(
                max_length=15,
                choices=[('youth', 'Youth'), ('children', 'Children')],
                default='youth',
            ),
        ),
    ]