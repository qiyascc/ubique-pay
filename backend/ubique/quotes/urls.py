from django.urls import path

from .views import QuoteView

urlpatterns = [
    path("", QuoteView.as_view(), name="quote"),
]
