from django.core.management.base import BaseCommand
from catalog.models import Book
from catalog.utils import generate_barcode_number

class Command(BaseCommand):
    help = 'Generates EAN-13 barcodes for all books that do not have one.'

    def handle(self, *args, **options):
        books_without_barcode = Book.objects.filter(barcode__isnull=True)
        count = books_without_barcode.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("All books already have barcodes."))
            return

        self.stdout.write(f"Found {count} books without barcodes. Generating...")

        updated = 0
        for book in books_without_barcode:
            if not book.barcode:
                barcode_num = generate_barcode_number(book.pk)
                book.barcode = barcode_num
                # Use update to avoid triggering signals/waitlist logic
                Book.objects.filter(pk=book.pk).update(barcode=barcode_num)
                updated += 1
                self.stdout.write(f"Generated barcode {barcode_num} for book ID {book.pk}")

        self.stdout.write(self.style.SUCCESS(f"Successfully generated barcodes for {updated} books."))
