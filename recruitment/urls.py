
from rest_framework.routers import DefaultRouter
from .views import RecruiterViewSet, TrialRequestViewSet

router = DefaultRouter()
router.register(r'recruiters', RecruiterViewSet, basename='recruiter')
router.register(r'trial-requests', TrialRequestViewSet, basename='trialrequest')

urlpatterns = router.urls
