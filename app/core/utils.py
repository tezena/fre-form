from typing import List, Optional, Dict, Any

def mask_student_data(student, allowed_fields: Optional[List[str]]) -> Dict[str, Any]:
    """
    Converts a Student database model into a dictionary and applies Field-Level Security.
    """
    
    # --- HELPER: Safely convert nested database rows to dictionaries ---
    def safely_extract_nested(db_obj):
        if not db_obj:
            return None
        # Dynamically grabs all columns (street, city, phone, etc.) except the internal IDs
        return {
            column.name: getattr(db_obj, column.name) 
            for column in db_obj.__table__.columns 
            if column.name not in ['id', 'student_id']
        }

    # --- 1. BUILD THE FULL DICTIONARY ---
    student_dict = {
        # Core Database Fields (Corrected to match your actual model)
        "id": student.id,
        "full_name": student.full_name,
        "gender": student.gender.value if hasattr(student.gender, 'value') else student.gender,
        "dob": student.dob,
        "photo_url": student.photo_url,
        "category": student.category.value if hasattr(student.category, 'value') else student.category,
        "department_id": student.department_id,
        "is_active": student.is_active,
        
        # Metadata
        "created_by_id": getattr(student, "created_by_id", None),
        "created_at": getattr(student, "created_at", None),
        
        # Nested Relationships (Address, Family, Health, etc.)
        "address": safely_extract_nested(getattr(student, "address", None)),
        "family": safely_extract_nested(getattr(student, "family", None)),
        "education": safely_extract_nested(getattr(student, "education", None)),
        "health": safely_extract_nested(getattr(student, "health", None)),
        "spirituality": safely_extract_nested(getattr(student, "spirituality", None)),
    }
    
    # --- 2. SUPER ADMIN / PROFILE BUILDER OVERRIDE ---
    # If allowed_fields is explicitly None, it means they have unrestricted access.
    if allowed_fields is None:
        return student_dict
        
    # --- 3. APPLY THE MASK ---
    # Always guarantee 'id' is returned so the frontend has a key to click on, 
    # even if the Super Admin forgot to add it to the allowed list.
    masked_data = {"id": student.id}
    
    for field in allowed_fields:
        if field in student_dict and field != "id":
            masked_data[field] = student_dict[field]
            
    return masked_data