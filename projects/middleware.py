from django.shortcuts import redirect
from django.urls import reverse

class BlockSuperUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_superuser:
            if not request.path.startswith(reverse('admin:index')):
                return redirect(reverse('admin:login'))

        elif request.user.is_authenticated and not request.user.is_superuser:
            if request.path.startswith(reverse('admin:index')):
                return redirect('/')

        if request.path.startswith(reverse('admin:login')):
            return self.get_response(request)

        return self.get_response(request)

