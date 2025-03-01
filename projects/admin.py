from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Organization, Event, User, Membership

class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'organization', 'start_datetime', 'end_datetime')
    filter_horizontal = ('members',)

# Custom User Change Form
class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')

# Custom User Admin
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = UserCreationForm

    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'groups')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email', 'first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Role', {'fields': ('role',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )

    def get_queryset(self, request):
        """
        Exclude superusers from the queryset displayed in the admin.
        """
        queryset = super().get_queryset(request)
        return queryset.filter(is_superuser=False)

admin.site.register(User, CustomUserAdmin)

admin.site.register(Event, EventAdmin)
admin.site.register(Organization)
admin.site.register(Membership)
