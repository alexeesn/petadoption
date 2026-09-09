"""
Management command to seed realistic sample data for Pet Adoption Management System.
"""
import io
from datetime import date, timedelta
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.accounts.models import User
from apps.health.models import HealthRecord, Vaccination
from apps.packages.models import AdoptionPackage
from apps.pets.models import Pet, PetImage


def create_pet_placeholder_image(name: str, species: str, color_hex: str, text_color: str = "#FFFFFF") -> ContentFile:
    """Generate a clean, high-resolution pet card image with Pillow."""
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color=color_hex)
    draw = ImageDraw.Draw(img)

    draw.ellipse([(-50, -50), (250, 250)], fill=(255, 255, 255, 30))
    draw.ellipse([(600, 400), (900, 700)], fill=(255, 255, 255, 20))
    draw.ellipse([(550, -100), (850, 200)], fill=(0, 0, 0, 15))

    species_icon = {
        "dog": "🐶 DOG",
        "cat": "🐱 CAT",
        "rabbit": "🐰 RABBIT",
        "bird": "🦜 BIRD",
    }.get(species, "🐾 PET")

    draw.rounded_rectangle([(100, 120), (700, 480)], radius=24, fill=(255, 255, 255))
    draw.rounded_rectangle([(140, 160), (320, 210)], radius=12, fill=color_hex)

    try:
        font_large = ImageFont.truetype("arial.ttf", 48)
        font_sub = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((160, 172), species_icon, fill=text_color, font=font_small)
    draw.text((140, 240), name, fill="#1E293B", font=font_large)
    draw.text((140, 310), "Pet Adoption Management System", fill="#64748B", font=font_sub)
    draw.text((140, 360), "Ready for a loving forever home ❤️", fill="#94A3B8", font=font_sub)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return ContentFile(buffer.getvalue())


SAMPLE_PETS_1 = [
    {
        "name": "Max",
        "species": Pet.Species.DOG,
        "breed": "Golden Retriever",
        "age_months": 14,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.LARGE,
        "weight_kg": 28.5,
        "color": "Golden Cream",
        "description": "Max is an energetic, friendly Golden Retriever who loves fetching balls and swimming.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#D97706",
    },
    {
        "name": "Luna",
        "species": Pet.Species.CAT,
        "breed": "Persian Longhair",
        "age_months": 8,
        "gender": Pet.Gender.FEMALE,
        "size": Pet.Size.SMALL,
        "weight_kg": 3.2,
        "color": "Pure White",
        "description": "Luna is a gentle and calm Persian cat with striking blue eyes. Perfect companion.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#0284C7",
    },
    {
        "name": "Milo",
        "species": Pet.Species.DOG,
        "breed": "Beagle",
        "age_months": 24,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.MEDIUM,
        "weight_kg": 11.0,
        "color": "Tricolor (Black, Tan & White)",
        "description": "Milo has a curious nose and a huge heart. Very affectionate and treat-motivated.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#059669",
    },
    {
        "name": "Bella",
        "species": Pet.Species.DOG,
        "breed": "Siberian Husky",
        "age_months": 18,
        "gender": Pet.Gender.FEMALE,
        "size": Pet.Size.LARGE,
        "weight_kg": 22.0,
        "color": "Silver Grey & White",
        "description": "Bella is vocal, playful, and loves morning jogs and outdoor adventures.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": False,
        "adoption_fee": 500.00,
        "bg_color": "#4F46E5",
    },
    {
        "name": "Oliver",
        "species": Pet.Species.CAT,
        "breed": "Maine Coon Mix",
        "age_months": 36,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.MEDIUM,
        "weight_kg": 6.8,
        "color": "Orange Tabby",
        "description": "Oliver is a gentle giant with a majestic fluffy coat and friendly disposition.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#EA580C",
    },
    {
        "name": "Daisy",
        "species": Pet.Species.DOG,
        "breed": "Pembroke Welsh Corgi",
        "age_months": 12,
        "gender": Pet.Gender.FEMALE,
        "size": Pet.Size.SMALL,
        "weight_kg": 10.2,
        "color": "Fawn & White",
        "description": "Daisy is full of joy and charm! She knows basic commands and gets along great with kids.",
        "status": Pet.Status.PENDING,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#7C3AED",
    },
]

SAMPLE_PETS_2 = [
    {
        "name": "Charlie",
        "species": Pet.Species.DOG,
        "breed": "Aspin / Native Mix",
        "age_months": 30,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.MEDIUM,
        "weight_kg": 14.5,
        "color": "Warm Brown & Black",
        "description": "Charlie is extremely loyal, smart, and resilient. A wonderful and loving companion.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#B45309",
    },
    {
        "name": "Cleo",
        "species": Pet.Species.CAT,
        "breed": "Siamese",
        "age_months": 15,
        "gender": Pet.Gender.FEMALE,
        "size": Pet.Size.SMALL,
        "weight_kg": 3.6,
        "color": "Seal Point & Cream",
        "description": "Cleo is sleek, intelligent, and talkative. Loves perching on high spots and observing.",
        "status": Pet.Status.RESERVED,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#0D9488",
    },
    {
        "name": "Barnaby",
        "species": Pet.Species.RABBIT,
        "breed": "Holland Lop",
        "age_months": 10,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.SMALL,
        "weight_kg": 1.8,
        "color": "Smoky Ash Grey",
        "description": "Barnaby has adorable floppy ears and loves fresh timothy hay. Quiet and gentle.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#16A34A",
    },
    {
        "name": "Pip",
        "species": Pet.Species.BIRD,
        "breed": "Cockatiel",
        "age_months": 20,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.SMALL,
        "weight_kg": 0.1,
        "color": "Lutino Yellow & Orange",
        "description": "Pip whistles cheerful tunes and loves stepping up onto fingers for head scratches.",
        "status": Pet.Status.AVAILABLE,
        "is_vaccinated": False,
        "is_neutered": False,
        "adoption_fee": 0,
        "bg_color": "#CA8A04",
    },
    {
        "name": "Rocky",
        "species": Pet.Species.DOG,
        "breed": "German Shepherd",
        "age_months": 48,
        "gender": Pet.Gender.MALE,
        "size": Pet.Size.LARGE,
        "weight_kg": 34.0,
        "color": "Black & Tan",
        "description": "Rocky is undergoing mild physical therapy for a minor paw strain. Alert and loyal.",
        "status": Pet.Status.UNDER_MEDICAL_CARE,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#475569",
    },
    {
        "name": "Coco",
        "species": Pet.Species.CAT,
        "breed": "Domestic Shorthair",
        "age_months": 6,
        "gender": Pet.Gender.FEMALE,
        "size": Pet.Size.SMALL,
        "weight_kg": 2.2,
        "color": "Calico",
        "description": "Coco found her forever home recently! A sweet kitten full of playfulness and purrs.",
        "status": Pet.Status.ADOPTED,
        "is_vaccinated": True,
        "is_neutered": True,
        "adoption_fee": 0,
        "bg_color": "#DB2777",
    },
]

SAMPLE_PETS = SAMPLE_PETS_1 + SAMPLE_PETS_2

PACKAGES = [
    {
        "name": "Basic Adoption Package (Free)",
        "description": "Essential adoption package at zero cost. Includes standard shelter intake records, adoption certificate, and a welcome guide for new pet parents.",
        "price": 0.00,
        "inclusions": [
            "Official Adoption Certificate",
            "Health & Intake Summary Record",
            "Custom Pet Name Tag",
            "New Pet Parent Starter Guide PDF",
        ],
        "is_active": True,
    },
    {
        "name": "Essential Care Package",
        "description": "Covers essential first-month essentials including initial deworming booster, anti-rabies vaccination certificate, collar, and leash.",
        "price": 1200.00,
        "inclusions": [
            "Official Adoption Certificate",
            "Anti-Rabies Vaccination & Government Tag",
            "Comprehensive Internal Deworming Treatment",
            "Adjustable Collar & Heavy-Duty Leash",
            "1-Month Supply of Flea & Tick Spot-On Treatment",
        ],
        "is_active": True,
    },
    {
        "name": "Complete Wellness & Medical Package",
        "description": "Comprehensive premium package including full core vaccines, ISO microchip registration, complete blood chemistry panel, and spay/neuter voucher.",
        "price": 2800.00,
        "inclusions": [
            "Full Core Vaccine Series (DHPP / FVRCP)",
            "ISO 11784/11785 Compliant Microchip & Lifetime Registry",
            "Spay / Neuter Procedure & Recovery Meds",
            "Complete Veterinary Health Certificate",
            "Premium Starter Food (3kg bag)",
            "30-Day Post-Adoption Telehealth Support",
        ],
        "is_active": True,
    },
]


class Command(BaseCommand):
    help = "Seeds comprehensive sample pets, packages, health records, and vaccinations."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding adoption packages..."))
        for pkg_data in PACKAGES:
            pkg, created = AdoptionPackage.objects.update_or_create(
                name=pkg_data["name"],
                defaults=pkg_data,
            )
            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  [{status_str}] Package: {pkg.name} (₱{pkg.price})")

        staff_user = User.objects.filter(role__in=["staff", "admin"]).first()
        today = timezone.now().date()

        self.stdout.write(self.style.NOTICE("Seeding pets, images, and health records..."))
        for pet_info in SAMPLE_PETS:
            pet_dict = dict(pet_info)
            bg_color = pet_dict.pop("bg_color")
            name = pet_dict["name"]

            pet, created = Pet.objects.update_or_create(
                name=name,
                defaults=pet_dict,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"  [{action}] Pet: {pet.name} ({pet.get_species_display()} - {pet.status})")

            # Seed primary image if missing
            if not pet.images.filter(is_primary=True).exists():
                img_file = create_pet_placeholder_image(pet.name, pet.species, bg_color)
                pet_img = PetImage(
                    pet=pet,
                    caption=f"{pet.name} - Primary Portrait",
                    is_primary=True,
                )
                pet_img.image.save(f"{pet.name.lower()}_primary.jpg", img_file, save=True)
                self.stdout.write(f"    + Added primary photo for {pet.name}")

            # Seed realistic health records and vaccinations
            if not pet.health_records.exists():
                HealthRecord.objects.create(
                    pet=pet,
                    veterinarian_name="Dr. Elena Santos, DVM",
                    veterinary_clinic="Metro Paws Animal Hospital",
                    diagnosis="General Wellness Intake Examination",
                    treatment="Clean bill of health, full physical check, ears and dental normal.",
                    notes=f"Patient {pet.name} is alert, active, and exhibits good coat condition.",
                    record_date=today - timedelta(days=20),
                    next_checkup_date=today + timedelta(days=160),
                    created_by=staff_user,
                )

            if not pet.vaccinations.exists():
                if pet.species in [Pet.Species.DOG, Pet.Species.CAT]:
                    Vaccination.objects.create(
                        pet=pet,
                        vaccine_name="Anti-Rabies Core",
                        date_administered=today - timedelta(days=60),
                        next_due_date=today + timedelta(days=305),
                        veterinarian="Dr. Elena Santos",
                        batch_number="RAB-2026-9921",
                        notes="Annual single dose administration",
                    )
                    core_name = "DHPP 5-in-1" if pet.species == Pet.Species.DOG else "FVRCP 4-in-1"
                    Vaccination.objects.create(
                        pet=pet,
                        vaccine_name=core_name,
                        date_administered=today - timedelta(days=340),
                        next_due_date=today + timedelta(days=25),
                        veterinarian="Dr. Elena Santos",
                        batch_number="COR-2025-4102",
                        notes="Booster scheduled soon",
                    )
                elif pet.species == Pet.Species.RABBIT:
                    Vaccination.objects.create(
                        pet=pet,
                        vaccine_name="RHDV2 (Rabbit Disease)",
                        date_administered=today - timedelta(days=90),
                        next_due_date=today + timedelta(days=275),
                        veterinarian="Dr. Elena Santos",
                        batch_number="RHD-2025-102",
                    )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {Pet.objects.count()} pets and {AdoptionPackage.objects.count()} packages!"))
