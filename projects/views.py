from http.client import responses
from lib2to3.fixes.fix_input import context
from pyexpat.errors import messages
from django.shortcuts import redirect
from django.urls import path


import json
import boto3
from allauth.conftest import user_with_recovery_codes
from botocore.config import Config
from django.conf import settings
from django.contrib.sites import requests
from django.shortcuts import render, HttpResponse
from urllib3 import request

from .forms import ClubFileForm
from .models import ClubFile, Event, RSVP

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from allauth.socialaccount.providers.google.views import  GoogleOAuth2Adapter
from allauth.socialaccount.helpers import complete_social_login

# Create your views here.
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template import loader
from django.db.models import F
from django.urls import reverse
from django.views import generic, View
from django.utils import timezone
from icalendar import Calendar, Event as ICalEvent
from django.utils.timezone import now
from django.urls import reverse_lazy
from django.db.models import Q
from django.views.generic.edit import CreateView
from django.views.generic import TemplateView
import logging
from allauth.socialaccount.providers.google.views import OAuth2LoginView

from projects.forms import EventForm, OrganizationForm, ClubFileForm
from projects.models import Organization, User, Event, Membership, Moderator, ClubFile, RSVP, JoinRequest
from datetime import timedelta
from django.http import JsonResponse
from django import forms


from django.views.generic import ListView

from projects.forms import EventForm, OrganizationForm
from projects.models import Organization, User, Event, Membership, Moderator, ChatMessage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core import serializers
from django.http import JsonResponse

def login_cancelled_redirect(request):
    return redirect('/')

# looked like eva is doing class-based view
class IndexView(generic.TemplateView):
    template_name = "projects/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        search_query = self.request.GET.get('search', '')

        if search_query:
            organizations = Organization.objects.filter(organization_name__icontains=search_query).distinct()
        else:
            organizations = Organization.objects.all().distinct()

        orgs = []
        orgs_list = []
        joined_orgs = []
        pending_requests = []
        user = self.request.user

        for org in organizations:
            if user.is_authenticated:
                is_member = Membership.objects.filter(user=user, organization=org).exists()
                has_pending_request = JoinRequest.objects.filter(
                    user=user, organization=org, status='pending'
                ).exists()

                if is_member:
                    joined_orgs.append({
                        'organization': org,
                        'is_member': True,
                    })
                elif has_pending_request:
                    pending_requests.append({
                        'organization': org,
                        'is_pending': True,
                    })
                else:
                    orgs_list.append({
                        'organization': org,
                        'is_member': False,
                    })

            orgs.append({
                'organization': org,
            })

        context['orgs'] = orgs
        context['orgs_list'] = orgs_list
        context['joined_orgs'] = joined_orgs
        context['search_query'] = search_query
        context['pending_requests'] = pending_requests

        return context

def google_login(request):
    return redirect('socialaccount_login', provider='google')
def google_signup(request):
    return redirect('socialaccount_login', 'google')

class OrganizationCreateView(generic.CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'projects/create_organization.html'
    success_url = reverse_lazy('projects:user_organizations_list')

    def form_valid(self, form):
        if Organization.objects.filter(organization_name=form.cleaned_data['organization_name']).exists():
            form.add_error('organization_name', 'An organization with this name already exists.')
            return self.form_invalid(form)

        form.instance.owner = self.request.user
        
        response = super().form_valid(form)

        Membership.objects.create(user=self.request.user, organization=self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing_organizations'] = Organization.objects.all()
        return context

class JoinOrganization(View):
    def post(self, request, org_id):
        organization = get_object_or_404(Organization, id=org_id)

        # Check if the user already has a pending or approved request
        if JoinRequest.objects.filter(user=request.user, organization=organization, status='pending').exists():
            print("you have a request")
            # messages.warning(request, "You already have a pending request to join this organization.")
        # elif organization.members.filter(id=request.user.id).exists():
        #     messages.warning(request, "You are already a member of this organization.")
        else:
            # Create a new join request
            JoinRequest.objects.create(user=request.user, organization=organization)
            print("request to join has been updated")
            # messages.success(request, "Your request to join has been submitted.")

        return HttpResponseRedirect(reverse('projects:index'))
       
class UserOrganizationsList(generic.ListView):
    model = Organization
    template_name = 'projects/user_organizations_list.html'
    context_object_name = 'organizations'

    def get_queryset(self):
        return Organization.objects.filter(membership__user=self.request.user).distinct()
        
class UserEventsList(generic.ListView):
    model = Event
    template_name = 'projects/user_events_list.html'
    context_object_name = 'events'
    paginate_by = 10

    def get_queryset(self):
        return Event.objects.filter(owner=self.request.user).order_by('start_datetime')

class AllEventsList(generic.ListView):
    model = Event
    template_name = 'projects/all_events_list.html'
    context_object_name = 'events'
    paginate_by = 10

    def get_queryset(self):
        return Event.objects.all().order_by('start_datetime')


@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    user = request.user
    organization = event.organization

    # Capture the referring URL
    prev_url = request.META.get('HTTP_REFERER', '/')

    # Handle form submission
    if request.method == "POST":
        # Exclude organization dynamically in the form
        form = EventForm(request.POST, request.FILES, instance=event)
        form.fields.pop('organization')
        if form.is_valid():
            # Save changes without altering the organization
            event = form.save(commit=False)
            event.organization = organization  # Retain original organization value

            # Retain the current image if no new image is uploaded
            if 'image' in request.FILES:
                image = request.FILES['image']
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                try:
                    # Save the file directly in the bucket without a folder
                    s3.upload_fileobj(image, settings.AWS_STORAGE_BUCKET_NAME, image.name)
                    event.image = image.name
                except Exception as e:
                    form.add_error('image', f"Image upload failed: {e}")
                    return render(request, 'projects/edit_event.html', {'form': form, 'event': event, 'prev_url': prev_url})

            event.save()
            return redirect('projects:members_org_events', org_id=organization.id) if organization else redirect('/user_events/')

    else:
        # Dynamically exclude the organization field for the edit form
        form = EventForm(instance=event)
        form.fields.pop('organization')  # Exclude organization field

    return render(
        request,
        'projects/edit_event.html',
        {
            'form': form,
            'event': event,
            'prev_url': prev_url,
            'organization': organization
        },
    )

class OrgEvents(generic.ListView):
    model = Event
    template_name = 'projects/org_events.html'
    context_object_name = 'events'
    paginate_by = 10
    


    def get_queryset(self):
        self.organization = get_object_or_404(Organization, id=self.kwargs['org_id'])
        return Event.objects.filter(organization=self.organization).order_by('start_datetime')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organization'] = self.organization
        context['organization_name'] = self.organization.organization_name
        context['organization_owner'] = self.organization.owner
        if self.request.user.is_authenticated:
            context['is_member'] = Membership.objects.filter(user=self.request.user, organization=self.organization).exists()
        else:
            context['is_member'] = False
        return context


class MembersOrgEvents(generic.ListView):
    model = Event
    template_name = 'projects/members_org_events.html'
    context_object_name = 'events'
    paginate_by = 10

    def get_queryset(self):
        self.organization = get_object_or_404(Organization, id=self.kwargs['org_id'])
        return Event.objects.filter(organization=self.organization).order_by('start_datetime')


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_moderator = Moderator.objects.filter(user=self.request.user, organization=self.organization).exists()

        context['organization'] = self.organization
        context['organization_name'] = self.organization.organization_name
        context['organization_owner'] = self.organization.owner
        context['is_member'] = Membership.objects.filter(user=self.request.user,organization=self.organization).exists()
        context['is_moderator'] = is_moderator

        return context


class OrgMembers(generic.ListView):
    model = Membership
    template_name = 'projects/org_members.html'
    context_object_name = 'members'
    paginate_by = 10
    

    def get_queryset(self):
        self.organization = get_object_or_404(Organization, id=self.kwargs['org_id'])
        return Membership.objects.filter(organization=self.organization)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organization'] = self.organization
        context['organization_name'] = self.organization.organization_name

        owner = self.organization.owner

        moderators = User.objects.filter(moderated_organizations__organization=self.organization)
        members_with_pics = []
        moderators_with_pics = []

        for membership in context['members']:
            user = membership.user
            user_is_moderator = user in moderators

            google_account = user.socialaccount_set.filter(provider='google').first()
            profile_pic_url = google_account.extra_data.get('picture') if google_account else None
            user_data = {
                'user': user,
                'profile_pic_url': profile_pic_url,
                'joined_on': membership.joined_on,
                'is_moderator': user_is_moderator
            }

            if user_is_moderator:
                moderators_with_pics.append(user_data)

            members_with_pics.append(user_data)



        current_user_info_member = next((member for member in members_with_pics if member['user'] == self.request.user),
                                        None)
        current_user_info_moderator = next(
            (moderator for moderator in moderators_with_pics if moderator['user'] == self.request.user), None)


        context['members_with_pics'] = members_with_pics
        context['moderators_with_pics'] = moderators_with_pics

        context['current_user_info_member'] = current_user_info_member
        context['current_user_info_moderator'] = current_user_info_moderator
        context['is_moderator'] = self.request.user in moderators
        context['is_owner'] = self.request.user == owner
        return context


# @login_required
# def join_organization(request, org_id):
#     organization = Organization.objects.get(id=org_id)
#     Membership.objects.get_or_create(user=request.user, organization=organization)
#     return redirect('projects:index')

@login_required
def leave_organization(request, org_id):
    organization = get_object_or_404(Organization, id=org_id)
    membership = Membership.objects.filter(user=request.user, organization=organization).first()

    if membership:
        membership.delete()

    referer = request.META.get('HTTP_REFERER', 'projects:profile')

    return redirect(referer)
    

@login_required
def delete_organization(request, org_id):
    config = Config(signature_version='s3v4')
    s3 = boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=config
    )
    organization = get_object_or_404(Organization, id=org_id)

    if request.user == organization.owner:
        files_to_delete = ClubFile.objects.filter(organization=organization)

        for file in files_to_delete:
            try:
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=file.name
                )
                file.delete() 
            except Exception as e:
                messages.error(request, f"Failed to delete file '{file.name}': {str(e)}")
        organization.delete()
    else:
        messages.error(request, "You do not have permission to delete this organization.")
    
    # referer = request.META.get('HTTP_REFERER', 'projects:profile')

    return redirect('projects:user_organizations_list')


@login_required
def delete_organization_pma(request, org_id):
    organization = get_object_or_404(Organization, id=org_id)
    config = Config(signature_version='s3v4')
    s3 = boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=config
    )
    files_to_delete = ClubFile.objects.filter(organization=organization)
    for file in files_to_delete:
            try:
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=file.name
                )
                file.delete() 
            except Exception as e:
                messages.error(request, f"Failed to delete file '{file.name}': {str(e)}")
    organization.delete()

    return redirect('/')

@login_required
def organization_detail(request, org_id):
    organization = get_object_or_404(Organization, id=org_id)
    moderators = organization.moderators.all()
    user_is_owner = request.user == organization.owner
    user_is_moderator = (request.user in moderators) or Moderator.objects.filter(user=request.user, organization=organization).exists()

    # user_is_moderator = moderators.filter(id=request.user.id).exists()
    # print(request.user.id)
    # print(moderators)
    # print(user_is_moderator)
    # print(Moderator.objects.filter(user=request.user, organization=organization))



    return render(request, 'projects/organization_detail.html', {
        'organization': organization,
        'moderators': moderators,
        'user_is_owner': user_is_owner,
        'user_is_moderator': user_is_moderator,
        # 'is_moderator': is_moderator
    })

@login_required
def manage_moderators(request, org_id):
    organization = get_object_or_404(Organization, id=org_id)

    if request.user != organization.owner:
        return redirect('projects:org_members', org_id=org_id)

    if request.method == 'POST':
        selected_user_ids = request.POST.getlist('moderators')
        selected_users = User.objects.filter(id__in=selected_user_ids)

        organization.moderators.all().delete()

        for user in selected_users:
            Moderator.objects.create(organization=organization, user=user)

        return redirect('projects:org_members', org_id=org_id)

    member_users = User.objects.filter(membership__organization=organization).exclude(id=organization.owner.id)

    owner =  User.objects.filter(id=organization.owner.id)

    current_moderators = organization.moderators.values_list('user__id', flat=True)

    return render(request, 'projects/manage_moderators.html', {
        'organization': organization,
        'members': member_users,
        'current_moderators': current_moderators,
    })

class EventView(generic.DetailView):
    model = Event
    template_name = 'projects/event_view.html'
    context_object_name = 'event'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['members_involved'] = self.object.members.all() if self.object.members.exists() else None
        rsvp_members = RSVP.objects.filter(event=self.object, status='going').select_related('user')
        context['rsvp_members'] = [rsvp.user for rsvp in rsvp_members]

        context['rsvp_status'] = 'going' if (self.request.user in context['rsvp_members']) else None
        context['user'] = self.request.user
        return context

@login_required
def fetch_chat_messages(request, organization_id, chat_type):
    user = request.user
    messages = ChatMessage.objects.filter(organization_id=organization_id, chat_type=chat_type).order_by('-timestamp')

    for message in messages:
        if user not in message.read_by.all():
            message.read_by.add(user)

    messages_list = [{'user': msg.user.username, 'message': msg.message, 'timestamp': msg.timestamp, 'read_by': [reader.username for reader in msg.read_by.all()]} for msg in messages]
    
    return JsonResponse({'messages': messages_list})

@login_required
def send_message(request, organization_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        chat_type = data.get('chat_type')
        message = data.get('message')
        user = request.user

        chat_message = ChatMessage(
            organization_id=organization_id,
            chat_type=chat_type,
            user=user,
            message=message
        )
        chat_message.save()

        return JsonResponse({'status': 'success', 'message': 'Message sent!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    
@login_required
def add_event(request, org_id=None):
    organization = None

    # Fetch organization if org_id is provided
    if org_id:
        organization = get_object_or_404(Organization, pk=org_id)
        if not Membership.objects.filter(user=request.user, organization=organization).exists():
            return redirect('projects:members_org_events', org_id=org_id)

    if request.method == 'POST':
        # Pre-fill organization value in POST data
        data = request.POST.copy()

        form = EventForm(data, request.FILES, user=request.user)
        if organization:
            data['organization'] = organization.id
            form.fields.pop('organization')


        if form.is_valid():
            event = form.save(commit=False)
            event.owner = request.user
            if organization:
                event.organization = organization

            else:
                event.organization = form.cleaned_data.get('organization', None)

            # Handle image upload to S3
            if 'image' in request.FILES:
                image = request.FILES['image']
                s3 = boto3.client('s3',
                                  aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                  aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
                s3.upload_fileobj(image, settings.AWS_STORAGE_BUCKET_NAME, f'event_images/{image.name}')
                event.image = f"event_images/{image.name}"

            event.save()
            return redirect('projects:members_org_events', org_id=org_id) if org_id else redirect('/user_events/')
    else:
        # Initialize the form
        initial_data = {'organization': organization} if organization else {}
        form = EventForm(initial=initial_data, user=request.user)

        # If organization is set, make it hidden
        if organization:
            form.fields.pop('organization')


    return render(request, 'projects/add_event.html', {
        'form': form,
        'organization': organization,
    })

@login_required
def delete_event(request, event_id, org_id):
    event = get_object_or_404(Event, pk=event_id)

    if request.method == 'POST':
        event.delete()
        return redirect(request.META.get('HTTP_REFERER', 'events'))

    return HttpResponseRedirect(reverse("projects:organization", args=(org_id,)))

@login_required
def delete_user_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    if request.method == 'POST':
        event.delete()
        return redirect('/user_events/')

    return HttpResponseRedirect(reverse("projects:user_events"))

#jackson ics feature 
def export_ics(request):
    # Create an iCalendar object
    cal = Calendar()
    cal.add('prodid', '-//PMA Event Manager//')
    cal.add('version', '2.0')

    # Get the user's upcoming events
    user = request.user
    upcoming_events = Event.objects.filter(owner=user, start_datetime__gte=now())

    # Add each event to the calendar
    for event in upcoming_events:
        ical_event = ICalEvent()
        ical_event.add('summary', event.name)
        ical_event.add('dtstart', event.start_datetime)  
        # Use event end_datetime, or default to 1 hour after start_datetime if not set
        end_time = event.end_datetime or (event.start_datetime + timedelta(hours=1))
        ical_event.add('dtend', end_time)  # Event end datetime 
        ical_event.add('location', event.location)
        cal.add_component(ical_event)

    # Prepare the .ics file
    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="upcoming_events.ics"'
    
    return response


def get_upcoming_events(user):
    current_time = timezone.now()

    owned_events = Event.objects.filter(owner=user, start_datetime__gte=current_time, end_datetime__gt=current_time)

    organization_ids = Membership.objects.filter(user=user).values_list('organization_id', flat=True)
    organization_events = Event.objects.filter(organization_id__in=organization_ids, start_datetime__gte=current_time,  end_datetime__gt=current_time)

    return owned_events | organization_events

def get_past_events(user):
    current_time = timezone.now()

    owned_events = Event.objects.filter(owner=user, end_datetime__lt=current_time, start_datetime__lt=current_time)

    organization_ids = Membership.objects.filter(user=user).values_list('organization_id', flat=True)
    organization_events = Event.objects.filter(organization_id__in=organization_ids, start_datetime__lt=current_time, end_datetime__lt=current_time)

    return owned_events | organization_events


def get_current_events(user):
    current_time = timezone.now()

    # Events owned by the user that are currently ongoing
    owned_events = Event.objects.filter(
        owner=user,
        start_datetime__lte=current_time,
        end_datetime__gt=current_time
    )

    # Get the organizations the user is a member of
    organization_ids = Membership.objects.filter(user=user).values_list('organization_id', flat=True)

    # Organization events that are currently ongoing
    organization_events = Event.objects.filter(
        organization_id__in=organization_ids,
        start_datetime__lte=current_time,
        end_datetime__gt=current_time
    )

    # Combine owned and organization events
    return owned_events | organization_events

def get_organizations(user):
    owned_organizations = Organization.objects.filter(owner=user)
    
    member_organizations = Organization.objects.filter(membership__user=user)
    
    organizations = (owned_organizations | member_organizations).distinct()
    
    return organizations


class ProfileView(generic.TemplateView):
    template_name = 'projects/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['upcoming_events'] = get_upcoming_events(user)
        context['past_events'] = get_past_events(user)
        context['current_events'] = get_current_events(user)
        context['organizations'] = get_organizations(user)

        google_account = user.socialaccount_set.filter(provider='google').first()
        profile_pic_url = google_account.extra_data.get('picture') if google_account else None
        context['profile_pic_url'] = profile_pic_url

        return context

logger = logging.getLogger(__name__)

def club_files(request, organization_id):
    error_message = ''
    search_query = request.GET.get('search', '').strip()
    organization = get_object_or_404(Organization, id=organization_id)
    files = ClubFile.objects.filter(organization_id=organization_id)

    is_moderator = Moderator.objects.filter(user=request.user, organization=organization).exists()


    # implements the search functionality from the requirements change
    if search_query:
        files = files.filter(
            Q(title__icontains=search_query) | Q(keywords__icontains=search_query)
        )

    config = Config(signature_version='s3v4')

    s3 = boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=config
    )

    # Handle file deletion
    if request.method == 'POST' and 'delete_file' in request.POST:
        file_id = request.POST.get('delete_file')
        file_to_delete = get_object_or_404(ClubFile, id=file_id)
        try:
            s3.delete_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_to_delete.name
            )
            file_to_delete.delete()
        except Exception as e:
            return HttpResponse(f"Failed to delete: {str(e)}")

        return redirect(request.path_info)

    # Handle file uploads
    if request.method == 'POST' and 'file' in request.FILES:
        form = ClubFileForm(request.POST, request.FILES)
        print(form.is_valid())
        if form.is_valid():
            print("Form was valid")
            uploaded_file = form.save(commit=False)
            uploaded_file.organization_id = organization_id
            file = request.FILES['file']
            if ClubFile.objects.filter(name=file.name, organization_id=organization_id).exists():
                error_message = "A file with this name already exists. Please rename your file and try again."
            else:
                try:
                    s3.upload_fileobj(
                        file,
                        settings.AWS_STORAGE_BUCKET_NAME,
                        file.name,
                        ExtraArgs={'ContentType': file.content_type}
                    )
                    uploaded_file.name = file.name
                    uploaded_file.save()
                    return redirect(request.path_info)
                except Exception as e:
                    return HttpResponse(f"Failed to upload: {str(e)}")
    else:
        form = ClubFileForm()

    # Prepare a list of files with preview URLs
    file_data = []
    for file in files:
        file_name = file.name.lower() if file.name else "untitled_file"
        file_type = "unknown"

        response_content_type = "application/octet-stream"
        preview_url = None

        if file_name.endswith('.jpg') or file_name.endswith('.jpeg'):
            file_type = "image"
            response_content_type = "image/jpeg"
            preview_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file.name,
                        'ResponseContentDisposition': 'inline', 'ResponseContentType': response_content_type, },
            )
        elif file_name.endswith('.png'):
            file_type = "image"
            response_content_type = "image/png"
            preview_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file.name,
                        'ResponseContentDisposition': 'inline', 'ResponseContentType': response_content_type, },
            )
        elif file_name.endswith('.gif'):
            file_type = "image"
            response_content_type = "image/gif"
            preview_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file.name,
                        'ResponseContentDisposition': 'inline', 'ResponseContentType': response_content_type, },
            )
        elif file_name.endswith('.pdf'):
            file_type = "pdf"
            response_content_type = "application/pdf"
            preview_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file.name,
                        'ResponseContentDisposition': 'inline', 'ResponseContentType': response_content_type, },
            )
        elif file_name.endswith('.docx'):
            file_type = "document"
            response_content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            preview_url = None
        elif file_name.endswith('.xlsx'):
            file_type = "document"
            response_content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            preview_url = None
        elif file_name.endswith('.txt'):
            file_type = "text"
            response_content_type = "text/plain"
            preview_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file.name,
                        'ResponseContentDisposition': 'inline', 'ResponseContentType': response_content_type, },
            )
        elif file_name.endswith('.mp3'):
            file_type = "audio"
            response_content_type = "audio/mpeg"
            preview_url = None
        elif file_name.endswith('.mp4'):
            file_type = "video"
            response_content_type = "video/mp4"
            preview_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file.name,
                        'ResponseContentDisposition': 'inline', 'ResponseContentType': response_content_type, },
            )
        elif file_name.endswith('.zip'):
            file_type = "archive"
            response_content_type = "application/zip"
            preview_url = None

        file_data.append({
            'id': file.id,
            'name': file.name,
            'timestamp': file.timestamp,
            'title': file.title,
            'description': file.description,
            'keywords': file.keywords,
            'url': f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file.name}",
            'type': file_type,
            'preview_url': preview_url,
        })

    return render(request, 'projects/club_files.html', {
        'organization': organization,
        'form': form,
        'files': file_data,
        'error_message': error_message,
        'search_query': search_query,
        'is_moderator': is_moderator
    })

def edit_file(request, organization_id, file_id):
    file = get_object_or_404(ClubFile, id=file_id)

    if request.method == 'POST':
        form = ClubFileForm(request.POST, instance=file)
        if form.is_valid():
            form.save()
            return redirect('projects:club_files', organization_id=file.organization_id)
    else:
        form = ClubFileForm(instance=file)

    return render(request, 'projects/edit_file.html', {
        'form': form,
        'file': file
    })

def notifications(request):
    now = timezone.now()
    twelve_hour_later = now + timezone.timedelta(hours=12)

    reminder_events = request.session.get('reminder_events', [])

    # Retrieve events happening within the next hour
    upcoming_events = Event.objects.filter(
        start_datetime__gte=now,
        start_datetime__lte=twelve_hour_later,
        id__in=reminder_events,
    )

    # Pass the count to the context
    return render(request, 'projects/notifications.html', {
        'upcoming_events': upcoming_events,
        'notification_count': upcoming_events.count()
    })

def get_notification_count(request):
    now = timezone.now()
    twelve_hour_later = now + timezone.timedelta(hours=12)

    reminder_events = request.session.get('reminder_events', [])
    if request.user.is_authenticated:
        return Event.objects.filter(
            start_datetime__gte=now,
            start_datetime__lte=twelve_hour_later,
            id__in=reminder_events,
        ).count()
    return 0

@csrf_exempt
@login_required
def toggle_reminder(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        event_id = data.get('event_id')
        
        if 'reminder_events' not in request.session:
            request.session['reminder_events'] = []

        reminder_events = request.session['reminder_events']

        if event_id in reminder_events:
            # Remove reminder
            reminder_events.remove(event_id)
            status = "removed"
        else:
            # Add reminder
            reminder_events.append(event_id)
            status = "added"

        # Update session data
        request.session['reminder_events'] = reminder_events
        request.session.modified = True

        return JsonResponse({"status": "success", "action": status})

    return JsonResponse({"status": "error"}, status=400)


class EventCalendarView(TemplateView):
    template_name = 'projects/event_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Retrieve the user's organizations and related events
        user_org_ids = Membership.objects.filter(user=self.request.user).values_list('organization_id', flat=True)
        events = Event.objects.filter(organization_id__in=user_org_ids).order_by('start_datetime')

        # Annotate each event with the user's RSVP status
        for event in events:
            rsvp = RSVP.objects.filter(user=self.request.user, event=event).first()
            event.rsvp_status = rsvp.status if rsvp else None
            event.rsvp_members = list(event.rsvps.filter(status='going').values_list('user__username', flat=True))
        context['events'] = events  # Pass events with RSVP status to the template
        return context


@login_required
def event_calendar(request):
    
    events = Event.objects.filter(start_datetime__gte=now()).order_by('start_datetime')
    for event in events:
        # Add RSVP status for the logged-in user
        rsvp = RSVP.objects.filter(user=request.user, event=event).first()
        event.rsvp_status = rsvp.status if rsvp else 'not_going'

        # Add members who RSVP'd as "going"
        #event.rsvp_members = event.rsvps.filter(status='going').values_list('user__username', flat=True)
        event.rsvp_members = list(event.rsvps.filter(status='going').values_list('user__username', flat=True))
    return render(request, 'event_calendar.html', {'events': events})

@login_required
def rsvp_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    rsvp, created = RSVP.objects.get_or_create(user=request.user, event=event)

    if request.method == 'POST':
        # Toggle RSVP status
        if rsvp.status == 'going':
            rsvp.status = 'not_going'
        else:
            rsvp.status = 'going'
        rsvp.save()

    # Debugging: Check the RSVP status and "going" members
    print(f"RSVP Status for {request.user.username}: {rsvp.status}")
    going_members = list(event.rsvps.filter(status='going').values_list('user__username', flat=True))
    print(f"Going members for event {event.id}: {going_members}")

    return JsonResponse({'status': 'success', 'rsvp_status': rsvp.status,  'going_members': going_members})

@login_required
def get_events(request):
    user = request.user
    user_org_ids = Membership.objects.filter(user=user).values_list('organization_id', flat=True)
    events = Event.objects.filter(organization_id__in=user_org_ids, start_datetime__gte=now())
    events_data = [
        {
            "id": event.id,
            "title": event.name,
            "start": event.start_datetime.isoformat(),
            "end": event.end_datetime.isoformat(),
            "location": event.location,
            "rsvp": user in event.members.all(),
            "organization": event.organization.organization_name,
        }
        for event in events
    ]
    return JsonResponse(events_data, safe=False)

def org_settings(request, organization_id):
    organization = get_object_or_404(Organization, id=organization_id)
    error_message = None

    if request.method == "POST":
        organization.organization_name = request.POST.get('org_name')

        if 'thumbnail' in request.FILES:
            thumbnail = request.FILES['thumbnail']
            valid_mime_types = ['image/jpeg', 'image/png', 'image/gif']

            if thumbnail.content_type not in valid_mime_types:
                error_message = "Invalid file type. Provide a jpeg, png, or gif."
            else:
                s3 = boto3.client('s3',
                                  aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                  aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
                s3.upload_fileobj(thumbnail, settings.AWS_STORAGE_BUCKET_NAME, f'org_thumbnail/{thumbnail.name}')
                organization.thumbnail = f"org_thumbnail/{thumbnail.name}"

        if not error_message:
            organization.save()
            return redirect('projects:org_settings', organization.id)

    return render(request, 'projects/org_settings.html', {'organization': organization, 'error_message': error_message})

def org_overview(request, organization_id):
    organization = get_object_or_404(Organization, id=organization_id)
    is_owner = request.user == organization.owner
    is_moderator = request.user in organization.moderators.all()

    context = {
        'organization': organization,
        'can_edit': (is_owner or is_moderator) and not request.user.is_pma_admin(),
    }
    return render(request, 'projects/org_overview.html', context)

@login_required
def update_overview(request, organization_id):
    organization = get_object_or_404(Organization, id=organization_id)
    
    if request.user != organization.owner and request.user not in organization.moderators.all():
        return messages.error(request, "You do not have permission to modify this organization.")

    if request.method == 'POST':
        description = request.POST.get('description')
        organization.description = description
        organization.save()
        return redirect('projects:org_overview', organization_id=organization.id)
    
    return redirect('projects:org_overview', organization_id=organization.id)


class ManageJoinRequests(ListView):
    template_name = 'projects/org_manage_requests.html'
    context_object_name = 'join_requests'

    def get_queryset(self):
        organization = get_object_or_404(Organization, id=self.kwargs['org_id'])
        # Verify moderator access and `is_pma_admin`
        if (
            self.request.user == organization.owner or 
            self.request.user in organization.moderators.all() or 
            getattr(self.request.user, "is_pma_admin", False)  # Use getattr to avoid errors
        ):
            return JoinRequest.objects.filter(organization=organization, status='pending')
        return JoinRequest.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = get_object_or_404(Organization, id=self.kwargs['org_id'])

        # print("User:", self.request.user)
        # print("Owner:", organization.owner)
        # print("Moderators:", organization.moderators.all())
        # print("Is Owner:", self.request.user == organization.owner)
        # print("Is Moderator:", self.request.user in organization.moderators.all())
        # print(Moderator.objects.filter(user=self.request.user, organization=organization))

        context['organization'] = organization
        context['is_owner'] = self.request.user == organization.owner
        context['is_moderator'] = self.request.user in organization.moderators.all() or Moderator.objects.filter(user=self.request.user, organization=organization)

        return context
    
class UpdateJoinRequestStatus(View):
    def post(self, request, request_id, status):
        join_request = get_object_or_404(JoinRequest, id=request_id)
        organization = join_request.organization

        if status == 'approved':
            Membership.objects.get_or_create(user=join_request.user, organization=join_request.organization)
            join_request.status = 'approved'
        elif status == 'rejected':
            join_request.status = 'rejected'
        join_request.save()

        join_requests = JoinRequest.objects.filter(organization=organization, status='pending')
        context = {
            'organization': organization,
            'join_requests': join_requests,
        }

        return render(request, 'projects/org_manage_requests.html', context)