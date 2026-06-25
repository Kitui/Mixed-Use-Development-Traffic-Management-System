from django.db import models


class SystemSettings(models.Model):
    estate_name = models.CharField(max_length=120, default='Tilisi Estate Traffic Portal')
    logo_url = models.CharField(max_length=240, blank=True)
    contact_phone = models.CharField(max_length=40, default='+254 700 000 000')
    contact_email = models.EmailField(default='security@tilisi.co.ke')
    timezone_name = models.CharField(max_length=80, default='Africa/Nairobi')
    default_theme = models.CharField(
        max_length=20,
        choices=(('light', 'Light'), ('dark', 'Dark')),
        default='light',
    )
    compact_mode = models.BooleanField(default=False)
    sms_simulation_enabled = models.BooleanField(default=True)
    email_simulation_enabled = models.BooleanField(default=False)
    require_visitor_id = models.BooleanField(default=True)
    require_vehicle_details = models.BooleanField(default=False)
    max_visit_hours = models.PositiveIntegerField(default=8)
    session_timeout_minutes = models.PositiveIntegerField(default=60)
    failed_login_warning = models.BooleanField(default=True)
    default_report_days = models.PositiveIntegerField(default=30)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System setting'
        verbose_name_plural = 'System settings'

    def __str__(self):
        return self.estate_name

    @classmethod
    def current(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
