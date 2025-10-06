
from django.db import models
from clubs.models import Club

class NewsItem(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    content = models.TextField()
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, related_name='news')
    cover = models.ImageField(upload_to='news/', null=True, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title
