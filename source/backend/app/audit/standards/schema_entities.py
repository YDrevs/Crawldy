"""Типи schema.org, що позначають ідентичність: Organization і нащадки.

Джерело: ієрархія типів schema.org, версія 29.2
(https://schema.org/Organization, https://schema.org/LocalBusiness),
звірено 30 серпня 2026. Google прямо рекомендує «найконкретніший
застосовний підтип» (developers.google.com/search/docs/appearance/
structured-data/organization) — тож перелік мусить покривати ПІДТИПИ,
інакше ми караємо саме тих, хто виконав рекомендацію: на вибірці night3
AutoDealer, FastFoodRestaurant, AmusementPark, ShoppingCenter,
NewsMediaOrganization і CollegeOrUniversity діставали «немає
Organization».

Це вендорований знімок, а не «поширені типи на око», — урок ISO 15924:
хибне спрацювання на коректній розмітці дорожче за пропущену знахідку.
Порівняння робиться без регістру (`Website` у дикій природі трапляється
поруч із `WebSite`), тож зберігаємо канонічні імена, а звіряємо
casefold-ом.
"""

from __future__ import annotations

SOURCE = "https://schema.org/ (version 29.2)"
CHECKED = "2026-08-30"

# Organization та всі його нащадки за ієрархією schema.org.
ORGANIZATION_TYPES = frozenset({
    "Organization",
    # прямі діти
    "Airline", "Consortium", "Cooperative", "Corporation",
    "EducationalOrganization", "FundingScheme", "GovernmentOrganization",
    "LibrarySystem", "LocalBusiness", "MedicalOrganization", "NGO",
    "NewsMediaOrganization", "OnlineBusiness", "PerformingGroup",
    "PoliticalParty", "Project", "ResearchOrganization",
    "SearchRescueOrganization", "SportsOrganization", "WorkersUnion",
    # EducationalOrganization
    "CollegeOrUniversity", "ElementarySchool", "HighSchool", "MiddleSchool",
    "Preschool", "School",
    # OnlineBusiness
    "OnlineStore",
    # PerformingGroup
    "DanceGroup", "MusicGroup", "TheaterGroup",
    # Project
    "FundingAgency", "ResearchProject",
    # SportsOrganization
    "SportsTeam",
    # MedicalOrganization (перетини з LocalBusiness лишаємо один раз)
    "DiagnosticLab", "VeterinaryCare",
    # LocalBusiness: прямі діти
    "AnimalShelter", "ArchiveOrganization", "AutomotiveBusiness", "ChildCare",
    "Dentist", "DryCleaningOrLaundry", "EmergencyService", "EmploymentAgency",
    "EntertainmentBusiness", "FinancialService", "FoodEstablishment",
    "GovernmentOffice", "HealthAndBeautyBusiness",
    "HomeAndConstructionBusiness", "InternetCafe", "LegalService", "Library",
    "LodgingBusiness", "MedicalBusiness", "ProfessionalService",
    "RadioStation", "RealEstateAgent", "RecyclingCenter", "SelfStorage",
    "ShoppingCenter", "SportsActivityLocation", "Store", "TelevisionStation",
    "TouristInformationCenter", "TravelAgency",
    # AutomotiveBusiness
    "AutoBodyShop", "AutoDealer", "AutoPartsStore", "AutoRental", "AutoRepair",
    "AutoWash", "GasStation", "MotorcycleDealer", "MotorcycleRepair",
    # EmergencyService
    "FireStation", "Hospital", "PoliceStation",
    # EntertainmentBusiness
    "AdultEntertainment", "AmusementPark", "ArtGallery", "Casino",
    "ComedyClub", "MovieTheater", "NightClub",
    # FinancialService
    "AccountingService", "AutomatedTeller", "BankOrCreditUnion",
    "InsuranceAgency",
    # FoodEstablishment
    "Bakery", "BarOrPub", "Brewery", "CafeOrCoffeeShop", "Distillery",
    "FastFoodRestaurant", "IceCreamShop", "Restaurant", "Winery",
    # GovernmentOffice
    "PostOffice",
    # HealthAndBeautyBusiness
    "BeautySalon", "DaySpa", "HairSalon", "HealthClub", "NailSalon",
    "TattooParlor",
    # HomeAndConstructionBusiness
    "Electrician", "GeneralContractor", "HVACBusiness", "HousePainter",
    "Locksmith", "MovingCompany", "Plumber", "RoofingContractor",
    # LegalService
    "Attorney", "Notary",
    # LodgingBusiness
    "BedAndBreakfast", "Campground", "Hostel", "Hotel", "Motel", "Resort",
    "SkiResort", "VacationRental",
    # MedicalBusiness
    "CommunityHealth", "Dermatology", "DietNutrition", "Emergency",
    "Geriatric", "Gynecologic", "MedicalClinic", "Midwifery", "Nursing",
    "Obstetric", "Oncologic", "Optician", "Optometric", "Otolaryngologic",
    "Pediatric", "Pharmacy", "Physician", "PhysicianIndividual",
    "PhysicianOffice", "Physiotherapy", "PlasticSurgery", "Podiatric",
    "PrimaryCare", "Psychiatric", "PublicHealth",
    # SportsActivityLocation
    "BowlingAlley", "ExerciseGym", "GolfCourse", "PublicSwimmingPool",
    "SportsClub", "StadiumOrArena", "TennisComplex",
    # Store
    "BikeStore", "BookStore", "ClothingStore", "ComputerStore",
    "ConvenienceStore", "DepartmentStore", "ElectronicsStore", "Florist",
    "FurnitureStore", "GardenStore", "GroceryStore", "HardwareStore",
    "HobbyShop", "HomeGoodsStore", "JewelryStore", "LiquorStore",
    "MensClothingStore", "MobilePhoneStore", "MovieRentalStore", "MusicStore",
    "OfficeEquipmentStore", "OutletStore", "PawnShop", "PetStore",
    "ShoeStore", "SportingGoodsStore", "TireShop", "ToyStore",
    "WholesaleStore",
})

# Ідентичність поза Organization: персональний бренд і сам сайт.
IDENTITY_TYPES = ORGANIZATION_TYPES | frozenset({"Person", "WebSite"})

_CASEFOLDED = frozenset(t.casefold() for t in IDENTITY_TYPES)

# Мінімальний розмір знімка — гард від мовчазного усічення при редагуванні.
EXPECTED_MIN_SIZE = 150


def is_identity_type(raw: str) -> bool:
    """Чи позначає тип ідентичність організації/особи/сайту. Без регістру."""
    return raw.casefold() in _CASEFOLDED


def registry_problems() -> list[str]:
    problems = []
    if len(IDENTITY_TYPES) < EXPECTED_MIN_SIZE:
        problems.append(
            f"знімок типів усічено: {len(IDENTITY_TYPES)} < {EXPECTED_MIN_SIZE}"
        )
    return problems


__all__ = [
    "CHECKED",
    "IDENTITY_TYPES",
    "ORGANIZATION_TYPES",
    "SOURCE",
    "is_identity_type",
    "registry_problems",
]
