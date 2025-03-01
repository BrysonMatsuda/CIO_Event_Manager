from django.test import TestCase, Client
from django.urls import reverse
from projects.models import Organization, User, Event, Membership, Organization, ChatMessage, ClubFile, RSVP
from projects.forms import OrganizationForm
from django.utils import timezone
from django.contrib.auth import get_user_model
import json
from unittest.mock import patch
from django.db import models
from django.utils.timezone import now
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile


User = get_user_model()

# testing org model
class OrganizationModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    def test_create_organization(self):
        org = Organization.objects.create(organization_name='Test Org', owner=self.user)
        self.assertEqual(org.organization_name, 'Test Org')
        self.assertEqual(org.owner, self.user)

# Test for organization views
class OrganizationViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')  

    def test_create_organization_view(self):
        # Create the organization with the created user as the owner
        response = self.client.post(reverse('projects:create_organization'), {
            'organization_name': 'Test Organization'
        })
        
        # Check for a successful redirect (302)
        self.assertEqual(response.status_code, 302)

        # Verify that the organization was created and is associated with the correct owner
        self.assertTrue(Organization.objects.filter(organization_name='Test Organization', owner=self.user).exists())


# Test for form validation
class OrganizationFormTest(TestCase):

    def test_valid_form(self):
        form_data = {'organization_name': 'Test Organization'}
        form = OrganizationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        form_data = {'organization_name': ''}
        form = OrganizationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('organization_name', form.errors)

# Test views.py 
class ChatTest(TestCase): 
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password') 
        self.organization = Organization.objects.create(organization_name="Test Organization", owner=self.user)

        Membership.objects.create(user=self.user, organization=self.organization)

        ChatMessage.objects.create(user=self.user, message="test", organization=self.organization, chat_type="general")
        ChatMessage.objects.create(user=self.user, message="bruh", organization=self.organization, chat_type="general")


    def test_fetch_chat_messages(self):
        # Test fetching chat messages
        url = reverse('projects:fetch_chat_messages', kwargs={'organization_id': self.organization.id, 'chat_type': 'general'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        messages = response.json().get('messages')

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['message'], "test")
        self.assertEqual(messages[1]['message'], "bruh")

    def test_send_chat_message(self):
        # Test sending a chat message
        url = reverse('projects:send_message', kwargs={'organization_id': self.organization.id})
        data = {
            'chat_type': 'general',
            'message': 'This is a test message.',
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'success')
        
        # Verify the message was saved in the database
        message_exists = ChatMessage.objects.filter(message="This is a test message.", organization=self.organization).exists()
        self.assertTrue(message_exists)

#test event
class EventModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.organization = Organization.objects.create(
            organization_name='Test Organization',  
            owner=self.user  
        )

    def test_event_creation(self):
        event = Event.objects.create(
            name='Test Event',
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
            location='Test Location',
            organization=self.organization,
            owner=self.user,
            image='event_images/test_image.jpeg'  # Assuming the image is saved as a string path
        )
        self.assertEqual(event.name, 'Test Event')
        self.assertEqual(event.location, 'Test Location')
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.owner, self.user)

    #may need test for required field and end time being valid
        
    def test_event_with_image(self):
        event = Event.objects.create(
            name='Event with Image',
            start_datetime=timezone.now(),
            end_datetime=timezone.now() + timezone.timedelta(hours=2),
            location='Test Location',
            organization=self.organization,
            owner=self.user,
            image='event_images/test_image.jpeg'
        )
        self.assertEqual(event.image, 'event_images/test_image.jpeg')

class ClubFileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.organization = Organization.objects.create(organization_name="Test Organization", owner=self.user)
        self.common_name = "example_file"
        self.common_title = "Example Title"
        self.common_description = "This is an example file description."
        self.common_keywords = "example, test"


    def test_clubfile_creation_with_all_fields(self):
        clubfile = ClubFile.objects.create(
            organization=self.organization,
            name=self.common_name,
            title=self.common_title,
            description=self.common_description,
            keywords=self.common_keywords,
        )
        self.assertEqual(clubfile.name, self.common_name)
        self.assertEqual(clubfile.title, self.common_title)
        self.assertEqual(clubfile.description, self.common_description)
        self.assertEqual(clubfile.keywords, self.common_keywords)
        self.assertIsNotNone(clubfile.timestamp)

    def test_clubfile_creation_without_title(self):
        clubfile = ClubFile.objects.create(
            organization=self.organization,
            name=self.common_name,
        )
        self.assertEqual(clubfile.title, self.common_name)

    def test_clubfile_str_representation(self):
        clubfile = ClubFile.objects.create(
            organization=self.organization,
            name=self.common_name,
        )
        self.assertEqual(str(clubfile), self.common_name)

    def test_clubfile_optional_fields(self):
        clubfile = ClubFile.objects.create(
            organization=self.organization,
            name=self.common_name,
        )
        self.assertIsNone(clubfile.description)
        self.assertIsNone(clubfile.keywords)


class RSVPModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.organization = Organization.objects.create(
        organization_name="Test Organization",
        owner=self.user,
        )
        self.event = Event.objects.create(
            name="Test Event",
            start_datetime=now(),
            end_datetime=now() + timedelta(hours=2),
             organization=self.organization,
        )

    def test_rsvp_creation(self):
        rsvp = RSVP.objects.create(user=self.user, event=self.event, status="going")
        self.assertEqual(rsvp.user, self.user)
        self.assertEqual(rsvp.event, self.event)
        self.assertEqual(rsvp.status, "going")

    def test_rsvp_unique_together(self):
        RSVP.objects.create(user=self.user, event=self.event, status="going")
        with self.assertRaises(Exception): 
            RSVP.objects.create(user=self.user, event=self.event, status="not_going")

    def test_rsvp_str_representation(self):
        rsvp = RSVP.objects.create(user=self.user, event=self.event, status="going")
        expected_str = f"{self.user.username} RSVP for {self.event.name} (going)"
        self.assertEqual(str(rsvp), expected_str)


class OrganizationSettingsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

        self.organization = Organization.objects.create(
            organization_name='Test Organization',
            owner=self.user
        )

    def test_change_organization_name(self):
        url = reverse('projects:org_settings', args=[self.organization.id])
        response = self.client.post(url, {'org_name': 'New Organization Name'})
        self.assertEqual(response.status_code, 302)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.organization_name, 'New Organization Name')

    def test_delete_organization(self):
        url = reverse('projects:delete_organization', args=[self.organization.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Organization.objects.filter(id=self.organization.id).exists())


class ClubFileMetadataTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        self.organization = Organization.objects.create(organization_name='Test Organization')
        self.club_files_url = reverse('projects:club_files', args=[self.organization.id])

    def test_add_metadata(self):
        dummy_file = SimpleUploadedFile("testfile.txt", b"File content", content_type="text/plain")

        file_data = {
            'file': dummy_file,
            'title': 'Test File Title',
            'description': 'A description for the test file.',
            'keywords': 'test, file, metadata'
        }

        self.client.post(self.club_files_url, data=file_data)
        file = ClubFile.objects.get(title='Test File Title')
        self.assertEqual(file.description, 'A description for the test file.')
        self.assertEqual(file.keywords, 'test, file, metadata')

    def test_edit_metadata(self):
        file = ClubFile.objects.create(
            title='Original Title',
            description='Original Description',
            keywords='original, metadata',
            organization=self.organization
        )

        edit_url = reverse('projects:edit_file', args=[self.organization.id, file.id])

        updated_data = {
            'title': 'Updated Title',
            'description': 'Updated Description',
            'keywords': 'updated, metadata'
        }

        self.client.post(edit_url, data=updated_data)

        file.refresh_from_db()
        self.assertEqual(file.title, 'Updated Title')
        self.assertEqual(file.description, 'Updated Description')
        self.assertEqual(file.keywords, 'updated, metadata')
