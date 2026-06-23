# Generated manually
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_member_custom_flyer_member_gender_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='lock_timeout',
            field=models.IntegerField(choices=[(5, '5 Minutes'), (15, '15 Minutes'), (60, '60 Minutes')], default=15),
        ),
    ]
