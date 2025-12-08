from django.core.management.base import BaseCommand
from ads.models import Ad

class Command(BaseCommand):
    help = "Seed initial ads"

    def handle(self, *args, **options):
        ad_id = "silkcoat-home-1"
        ad, created = Ad.objects.update_or_create(
            ad_id=ad_id,
            defaults={
                "title": "Silkcoat - Promo",
                "image": "https://kanousport.com/media/ads/silkcoat-banner.jpg",
                "video": "https://www.youtube.com/embed/VID_ID",  # remplace VID_ID
                "link": "https://silkcoat.example.com/produits",
                "active": True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created {ad_id}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {ad_id}"))
