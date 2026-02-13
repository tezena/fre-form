from enum import Enum

class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class StudentCategory(str, Enum):
    CHILDREN = "CHILDREN"
    ADOLESCENT = "ADOLESCENT"
    YOUTH = "YOUTH"
    ADULT = "ADULT"



class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    MONK = "MONK" # "Menokusie" if relevant

class EducationLevel(str, Enum):
    ELEMENTARY = "ELEMENTARY"
    HIGH_SCHOOL = "HIGH_SCHOOL"
    PREPARATORY = "PREPARATORY"
    HIGHER_EDUCATION = "HIGHER_EDUCATION"
    ILLITERATE = "ILLITERATE"

class OccupationStatus(str, Enum):
    STUDENT = "STUDENT"
    EMPLOYED_CIVIL = "EMPLOYED_CIVIL"
    EMPLOYED_PRIVATE = "EMPLOYED_PRIVATE"
    WORKER_AND_STUDENT = "WORKER_AND_STUDENT"
    UNEMPLOYED = "UNEMPLOYED"
    SELF_EMPLOYED = "SELF_EMPLOYED"

class ChurchAttendance(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    OCCASIONALLY = "OCCASIONALLY"
    NEVER = "NEVER"