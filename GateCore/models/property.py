from django.db import models
from .base import BaseModel

class Site(BaseModel):
    SITE_TYPES = [
        ("estate", "Estate"),
        ("office_park", "Office Park"),
        ("mixed_use", "Mixed Use"),
        ("industrial", "Industrial"),
        ("campus", "Campus"),
    ]
    name = models.CharField(max_length=255)
    site_type = models.CharField(max_length=50, choices=SITE_TYPES)
    location = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['site_type', 'is_active']),
        ]
    def __str__(self):
        return f"{self.name} ({self.get_site_type_display()})"

class Property(BaseModel):
    PROPERTY_TYPES = [
        ("residential", "Residential"),
        ("commercial", "Commercial"),
        ("mixed", "Mixed"),
        ("industrial", "Industrial"),
        ("retail", "Retail"),
    ]
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="properties"
    )
    name = models.CharField(max_length=255)
    property_code = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField()
    property_type = models.CharField(max_length=50, choices=PROPERTY_TYPES)
    location = models.CharField(max_length=255, blank=True)
    total_units = models.IntegerField(default=0)
    total_floors = models.IntegerField(default=1)
    year_built = models.IntegerField(null=True, blank=True)
    class Meta:
        ordering = ['site', 'name']
        verbose_name_plural = "Properties"
        unique_together = ["site", "property_code"]
        indexes = [
            models.Index(fields=['site', 'property_type']),
            models.Index(fields=['property_type', 'is_active']),
        ]
    def __str__(self):
        return f"{self.name} - {self.site.name}"

class Unit(BaseModel):
    UNIT_TYPES = [
        ("house", "House"),
        ("apartment", "Apartment"),
        ("office", "Office"),
        ("shop", "Shop"),
        ("warehouse", "Warehouse"),
        ("studio", "Studio"),
        ("penthouse", "Penthouse"),
    ]
    STATUS_CHOICES = [
        ("vacant", "Vacant"),
        ("occupied", "Occupied"),
        ("maintenance", "Under Maintenance"),
        ("reserved", "Reserved"),
        ("unavailable", "Unavailable"),
    ]
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="units"
    )
    unit_code = models.CharField(max_length=50)
    unit_type = models.CharField(max_length=50, choices=UNIT_TYPES)
    floor = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="vacant")
    area_sqft = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    bedrooms = models.IntegerField(default=0)
    bathrooms = models.IntegerField(default=1)
    access_code = models.CharField(max_length=20, blank=True, null=True)
    has_parking = models.BooleanField(default=False)
    parking_spots = models.IntegerField(default=0)
    class Meta:
        ordering = ['property', 'floor', 'unit_code']
        unique_together = ["property", "unit_code"]
        indexes = [
            models.Index(fields=['property', 'status']),
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['floor', 'unit_type']),
        ]
    def __str__(self):
        return f"{self.unit_code} - {self.property.name}"
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.property:
            self.property.total_units = self.property.units.count()
            self.property.save(update_fields=['total_units'])
