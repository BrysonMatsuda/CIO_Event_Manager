from django.urls import path, include

from . import views
from .views import UserEventsList, AllEventsList, OrgEvents, rsvp_event, ManageJoinRequests, UpdateJoinRequestStatus, \
login_cancelled_redirect

app_name = "projects"
urlpatterns = [
    path('events/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path("", views.IndexView.as_view(), name="index"),
    path('create/', views.OrganizationCreateView.as_view(), name='create_organization'),
    path('organization/<int:org_id>/join/', views.JoinOrganization.as_view(), name='join_organization'),
    path('leave_organization/<int:org_id>/', views.leave_organization, name='leave_organization'),
    path('delete_organization/<int:org_id>/', views.delete_organization, name='delete_organization'),
    path('add_event/', views.add_event, name='add_event'),
    path('user_organizations/', views.UserOrganizationsList.as_view(), name='user_organizations_list'),
    path('user_events/', views.UserEventsList.as_view(), name='user_events_list'),
    path('organization/<int:org_id>/events/<int:event_id>/delete_event/', views.delete_event, name='delete_event'),
    path('user_events/<int:event_id>/delete_event/', views.delete_user_event, name='delete_user_event'),
    path('event_view/<int:pk>/', views.EventView.as_view(), name='event_view'),
    path('all_events/', views.AllEventsList.as_view(), name='all_events_list'),
    path('organization/<int:org_id>/events/', views.OrgEvents.as_view(), name='org_events'),
    path('organization/<int:org_id>/members_events/', views.MembersOrgEvents.as_view(), name='members_org_events'),
    path('accounts/login/', views.google_login, name='account_login'),
    path('accounts/signup/', views.google_signup, name='account_signup'),
    path('organization/<int:org_id>/', views.organization_detail, name='organization_detail'),
    path('organization/<int:org_id>/manage-moderators/', views.manage_moderators, name='manage_moderators'),
    path('clubs/<int:organization_id>/files/', views.club_files, name='club_files'),
    path('clubs/<int:organization_id>/files/edit/<int:file_id>/', views.edit_file, name='edit_file'),
    path('fetch_chat_messages/<int:organization_id>/<str:chat_type>/', views.fetch_chat_messages, name='fetch_chat_messages'),
    path('send-message/<int:organization_id>/', views.send_message, name='send_message'),
    path('delete_organization_pma/<int:org_id>/', views.delete_organization_pma, name='delete_organization_pma'),
    path('notifications/', views.notifications, name='notifications'),
    path('toggle_reminder/', views.toggle_reminder, name='toggle_reminder'),
    path('event-calendar/', views.EventCalendarView.as_view(), name='event_calendar'),
    path('rsvp-event/<int:event_id>/', views.rsvp_event, name='rsvp_event'),
    path('get-events/', views.get_events, name='get_events'),
    path('organization/<int:org_id>/members/', views.OrgMembers.as_view(), name='org_members'),
    path('add_event/<int:org_id>/', views.add_event, name='add_event_for_org'),
    path('<int:organization_id>/overview/', views.org_overview, name='org_overview'),
    path('<int:organization_id>/settings/', views.org_settings, name='org_settings'),
    path('<int:organization_id>/update_overview/', views.update_overview, name='update_overview'),
    path('organization/<int:org_id>/requests/', ManageJoinRequests.as_view(), name='org_manage_requests'),
    path('request/<int:request_id>/update/<str:status>/', UpdateJoinRequestStatus.as_view(), name='update_request_status'),
    path('rsvp/<int:event_id>/', views.rsvp_event, name='rsvp_event'),
    path('accounts/3rdparty/login/cancelled/', login_cancelled_redirect, name='account_cancelled_redirect'),
]
