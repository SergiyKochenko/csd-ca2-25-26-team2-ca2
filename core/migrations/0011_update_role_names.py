# Generated migration to update role names to proper English

from django.db import migrations


def forwards(apps, schema_editor):
    """Update role names to proper English: Housekeeper, Reception, Maintenance, Admin"""
    Role = apps.get_model('core', 'Role')
    db_alias = schema_editor.connection.alias
    
    # Define the mapping of old role names to new ones
    role_mapping = {
        'House Manager': 'Housekeeper',
        'House Cleaner': 'Housekeeper',
        'Housekeeping': 'Housekeeper',
        'Reception': 'Reception',
        'Maintenance': 'Maintenance',
        'Admin': 'Admin',
    }
    
    # Delete old role records
    Role.objects.using(db_alias).exclude(name__in=['Housekeeper', 'Reception', 'Maintenance']).delete()
    
    # Create the new standard roles if they don't exist
    roles_to_create = {
        'Housekeeper': 'staff',
        'Reception': 'staff',
        'Maintenance': 'staff',
    }
    
    for role_name, category in roles_to_create.items():
        Role.objects.using(db_alias).get_or_create(
            name=role_name,
            defaults={'category': category}
        )


def reverse(apps, schema_editor):
    # No reverse operation
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_role_alter_staff_role'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
