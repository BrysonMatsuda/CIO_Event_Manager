from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from s3direct.fields import S3DirectField
from datetime import datetime, timedelta

class User(AbstractUser):
    COMMON_USER = 'common_user'
    PMA_ADMIN = 'pma_admin'
    ROLE_CHOICES = [
        (COMMON_USER, 'Common User'),
        (PMA_ADMIN, 'PMA Admin'),
    ]

    date_joined = models.DateTimeField(auto_now_add=True)

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default=COMMON_USER)

    def is_pma_admin(self):
        return self.role == self.PMA_ADMIN

    def is_common_user(self):
        return self.role == self.COMMON_USER

class Organization(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_organizations', default=1)
    date_created = models.DateTimeField(auto_now_add=True, null=True)
    organization_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to='org_thumbnail/', blank=True, null=True)

    # just for debugging
    # def save(self, *args, **kwargs):
    #     print(self.thumbnail)
    #     if self.thumbnail:
    #         print(f"Uploading file with key: org_thumbnail/{self.thumbnail.name}")
    #     else:
    #         print('org created without image')
    #     super().save(*args, **kwargs)

    def __str__(self):
        return self.organization_name

class JoinRequest(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} -> {self.organization.name} ({self.status})"


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    joined_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user.username} - {self.organization.organization_name}"
    
class Event(models.Model):
    name = models.CharField(max_length=250)
    start_datetime = models.DateTimeField(default=datetime.now)  
    end_datetime = models.DateTimeField(default=datetime.now() + timedelta(hours=1))    
    location = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, default=1, on_delete=models.CASCADE)
    members = models.ManyToManyField(User, related_name='events', blank=True)
    image = models.ImageField(upload_to='event_images/', blank=True, null=True)
    sponsor = models.CharField(max_length=255, blank=True, null=True)  
    deliverable = models.TextField(blank=True, null=True)  

class Moderator(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='moderators')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='moderated_organizations')

    class Meta:
        unique_together = ('organization', 'user')

    def __str__(self):
        return f"{self.user.username} - {self.organization.organization_name}"
    
class ClubFile(models.Model):
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, null=True)
    file = models.FileField(upload_to='')
    file = S3DirectField(dest='primary_destination', blank=True)

    # Metadata from new requirements
    title = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(default=datetime.now)
    description = models.TextField(null=True, blank=True)
    keywords = models.CharField(max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        # If a title is not given, it defaults to the file's full name
        # I think this is preferable to forcing the user to add a title
        if not self.title:
            self.title = self.name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    chat_type = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True)
    read_by = models.ManyToManyField(User, related_name="read_messages", blank=True)

    def __str__(self):
        return f'{self.user.username}: {self.message[:50]}'
    
class RSVP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rsvps")
    status = models.CharField(
        max_length=10,
        choices=[('going', 'Going'), ('not_going', 'Not Going')],
        default='going'
    )

    class Meta:
        unique_together = ('user', 'event')  # Ensure a user can only RSVP once per event

    def __str__(self):
        return f"{self.user.username} RSVP for {self.event.name} ({self.status})"
