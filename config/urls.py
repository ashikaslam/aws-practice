from django.urls import path, include
from django.http import HttpResponse

urlpatterns = [
    path("", lambda request: HttpResponse("Hello World")),
    path("api/", include("core.urls")),
]
