# clubs/admin.py
from django.contrib import admin
from .models import Club, StaffMember


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "city", "president", "coach")
    search_fields = ("name", "short_name", "city")


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "role", "club", "phone", "email", "is_active")
    list_filter = ("role", "club", "is_active")
    search_fields = ("full_name", "email", "phone")
