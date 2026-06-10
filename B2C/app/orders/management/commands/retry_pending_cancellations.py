from django.core.management.base import BaseCommand

from app.orders.services import retry_pending_cancellations


class Command(BaseCommand):
    help = "Retry B2B unreserve for orders in CANCEL_PENDING status."

    def handle(self, *args, **options):
        cancelled_count = retry_pending_cancellations()
        self.stdout.write(
            self.style.SUCCESS(
                f"Retried pending cancellations; cancelled {cancelled_count} orders."
            )
        )
