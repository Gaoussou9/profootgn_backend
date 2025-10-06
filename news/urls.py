
from rest_framework.routers import DefaultRouter
from .views import NewsItemViewSet

router = DefaultRouter()
router.register(r'news', NewsItemViewSet, basename='news')

urlpatterns = router.urls
