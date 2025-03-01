from django.utils import timezone
from projects.models import Event, Moderator, Organization

def notification_count(request):
    if request.user.is_authenticated:
        now = timezone.now()
        twelve_hour_later = now + timezone.timedelta(hours=12)
        reminder_events = request.session.get('reminder_events', [])
        upcoming_events_count = Event.objects.filter(
            start_datetime__gte=now,
            start_datetime__lte=twelve_hour_later,
            id__in=reminder_events,
        ).count()
        return {'notification_count': upcoming_events_count}
    return {'notification_count': 0}


def organization_context(request):
    if not request.user.is_authenticated:
        return {}

    organization_id = request.resolver_match.kwargs.get('organization_id')
    if not organization_id:
        return {}

    try:
        organization = Organization.objects.get(id=organization_id)
        is_owner = request.user == organization.owner
        is_moderator = Moderator.objects.filter(user=request.user, organization=organization).exists()
        return {
            'organization': organization,
            'is_owner': is_owner,
            'is_moderator': is_moderator,
        }
    except Organization.DoesNotExist:
        return {}
    


