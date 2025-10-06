# clubs/urls.py
from rest_framework.routers import DefaultRouter
from .views import ClubViewSet, StaffMemberViewSet

router = DefaultRouter()
router.register(r"clubs", ClubViewSet, basename="club")
router.register(r"staff", StaffMemberViewSet, basename="staff")  # ← important

urlpatterns = router.urls
