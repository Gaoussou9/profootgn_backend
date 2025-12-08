from django.urls import path
from . import views

urlpatterns = [
    path("", views.list_ads, name="ads-list"),
    path("impression/", views.log_impression, name="ad-impression"),
    path("click/", views.log_click, name="ad-click"),
    path("create/", views.create_or_update_ad, name="ad-create"),
    path("stats/", views.get_stats, name="ad-stats"),
]
