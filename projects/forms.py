from django import forms
from django.forms import Textarea
from django.forms import FileField
from django.db import models

from .models import Event, Organization, ClubFile
from .models import Event, Organization
from django.forms.widgets import TextInput
from django.core.exceptions import ValidationError
from django.forms import DateTimeInput




class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user passed from the view
        super(EventForm, self).__init__(*args, **kwargs)

        if user:
            # Filter organizations where the user is a moderator
            self.fields['organization'].queryset = Organization.objects.filter(
                moderators__user=user
            )
    start_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control datetimepicker',
            'placeholder': 'Start Date and Time'
        }),
        label='Start Date and Time',
        input_formats=['%Y-%m-%d %I:%M %p']  # Matches Flatpickr format (12-hour with AM/PM)
    )

    end_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control datetimepicker',
            'placeholder': 'End Date and Time'
        }),
        label='End Date and Time',
        input_formats=['%Y-%m-%d %I:%M %p']  # Matches Flatpickr format (12-hour with AM/PM)
    )

    organization = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        to_field_name='organization_name',
        empty_label="Select an organization",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    image = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user passed from the view
        super(EventForm, self).__init__(*args, **kwargs)

        if user:
            # Filter organizations based on the user's membership
            self.fields['organization'].queryset = Organization.objects.filter(
                membership__user=user  # Only organizations the user is a member of
            )

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')

        if not start_datetime:
            self.add_error('start_datetime', "Start date and time is required.")

        if not end_datetime:
            self.add_error('end_datetime', "End date and time is required.")

        if start_datetime and end_datetime and start_datetime >= end_datetime:
            self.add_error('start_datetime', "Start date and time must be before end date and time.")
            self.add_error('end_datetime', "End date and time must be after start date and time.")

        return cleaned_data

    class Meta:
        model = Event
        fields = ['name', 'start_datetime', 'end_datetime', 'location', 'organization', 'image', 'sponsor', 'deliverable']
        widgets = {
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Name'}),
            'location': TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
            'sponsor': TextInput(attrs={'class': 'form-control', 'placeholder': 'Sponsor'}),
            'deliverable': Textarea(attrs={'class': 'form-control', 'placeholder': 'Deliverable'}),
        }


class OrganizationForm(forms.ModelForm):
    organization_name = forms.CharField(
        max_length=22, 
        widget=forms.TextInput(
            attrs={
                'class': 'form-control', 
                'placeholder': 'Enter organization name (Max 22 Characters)'
            }
        )
    )

    class Meta:
        model = Organization
        fields = ['organization_name']

class ClubFileForm(forms.ModelForm):
    class Meta:
        model = ClubFile
        fields = ['title', 'file', 'description', 'keywords']  # Added metadata to form upload

    def save(self, commit=True):
        # Get the instance to be saved
        club_file_instance = super().save(commit=False)

        # Set the file_name to the name of the uploaded file
        if self.cleaned_data['file']:
            club_file_instance.name = self.cleaned_data['file'].name

        if commit:
            club_file_instance.save()  # Save the instance if required

        return club_file_instance
