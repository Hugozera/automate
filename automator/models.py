from django.db import models
import json

class AutomationLog(models.Model):
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, default='INFO')
    
    def __str__(self):
        return f"[{self.timestamp}] {self.message}"

class ShopifyAccount(models.Model):
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.email} - {self.phone}"