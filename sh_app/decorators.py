from django.http import HttpRequest
from django.shortcuts import redirect


def allowed_users(allowed_roles=[]):
    def decorator(view_func):
        def wrapper_func(request: HttpRequest, *args, **kwargs):
            if request.user.groups.exists():
                group = request.user.groups.all()[0].name
                if group in allowed_roles:
                    return view_func(request, *args, **kwargs)
                else:
                    return redirect('unauthorized')
            else:
                return redirect('unauthorized')
        return wrapper_func
    return decorator

