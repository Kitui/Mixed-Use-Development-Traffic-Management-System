from django.db import migrations


def clear_unit_log_gates(apps, schema_editor):
    TrafficLog = apps.get_model('traffic_logs', 'TrafficLog')
    TrafficLog.objects.filter(checkpoint_type='COMMUNITY_UNIT').update(gate='')


def restore_default_gate(apps, schema_editor):
    TrafficLog = apps.get_model('traffic_logs', 'TrafficLog')
    TrafficLog.objects.filter(checkpoint_type='COMMUNITY_UNIT', gate='').update(gate='CHUNGA_MALI')


class Migration(migrations.Migration):

    dependencies = [
        ('traffic_logs', '0003_alter_trafficlog_gate'),
    ]

    operations = [
        migrations.RunPython(clear_unit_log_gates, restore_default_gate),
    ]
