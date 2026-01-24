# Sunday School Management System - Backend API

A production-grade FastAPI backend for managing Sunday School operations with complex Role-Based Access Control (RBAC).

## Tech Stack

- **Framework**: FastAPI (async/await)
- **Database**: PostgreSQL
- **ORM**: SQLModel (combines Pydantic & SQLAlchemy)
- **Migrations**: Alembic
- **Authentication**: OAuth2 with JWT (python-jose, passlib[bcrypt])
- **Validation**: Pydantic V2
- **Environment**: pydantic-settings

## Features

### Role-Based Access Control (RBAC)

1. **Super Admin**
   - Full access to all resources
   - Can create/update/delete Users, Departments, and Students
   - Can create Admins

2. **Admin**
   - Assigned to specific Departments
   - Can only create/remove Managers within their assigned departments
   - Can view/edit Students in their assigned departments
   - Cannot manage other users (except Managers in their departments)

3. **Manager**
   - Assigned to specific Departments
   - Can only view/edit Student data within their assigned departments
   - Cannot manage other users

## Project Structure

```
sunday_school_backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py          # Authentication endpoints
│   │       │   ├── users.py         # User management
│   │       │   ├── students.py     # Student management
│   │       │   └── departments.py  # Department management
│   │       └── api.py               # API router
│   ├── core/
│   │   ├── config.py                # Application settings
│   │   ├── security.py              # JWT & password hashing
│   │   └── dependencies.py          # Auth & permission dependencies
│   ├── db/
│   │   ├── session.py               # Database session
│   │   └── base.py                  # Model imports for Alembic
│   ├── models/                      # SQLModel database models
│   │   ├── user.py
│   │   ├── department.py
│   │   └── student.py
│   ├── schemas/                     # Pydantic request/response models
│   │   ├── user.py
│   │   └── student.py
│   └── main.py                      # FastAPI application
├── alembic/                         # Database migrations
├── requirements.txt
├── docker-compose.yml
└── .env
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Installation

1. **Clone the repository and navigate to the project directory**

2. **Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env  # Edit .env with your settings
```

Update `.env` with your database credentials and secret key:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sunday_school_db
SECRET_KEY=your-secret-key-change-this-in-production
```

5. **Set up the database**

Using Docker Compose:
```bash
docker-compose up -d db
```

Or use your own PostgreSQL instance.

6. **Run migrations**
```bash
alembic upgrade head
```

7. **Start the development server**
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation:
- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`

## Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login and get JWT token

### Users
- `GET /api/v1/users/me` - Get current user info
- `POST /api/v1/users/` - Create user (Super Admin only)
- `POST /api/v1/users/admin/create-manager` - Create Manager (Admin/Super Admin)
- `GET /api/v1/users/` - List all users (Super Admin only)
- `GET /api/v1/users/{user_id}` - Get user (Super Admin only)
- `PUT /api/v1/users/{user_id}` - Update user (Super Admin only)
- `DELETE /api/v1/users/{user_id}` - Delete user (Super Admin only)

### Departments
- `POST /api/v1/departments/` - Create department (Super Admin only)
- `GET /api/v1/departments/` - List departments
- `GET /api/v1/departments/{department_id}` - Get department
- `PUT /api/v1/departments/{department_id}` - Update department (Super Admin only)
- `DELETE /api/v1/departments/{department_id}` - Delete department (Super Admin only)

### Students
- `POST /api/v1/students/` - Create student
- `GET /api/v1/students/` - List students (filtered by permissions)
- `GET /api/v1/students/{student_id}` - Get student
- `PUT /api/v1/students/{student_id}` - Update student
- `DELETE /api/v1/students/{student_id}` - Delete student (Super Admin only)

## Authentication

All endpoints (except `/auth/login`) require authentication via Bearer token:

```bash
curl -H "Authorization: Bearer <your-jwt-token>" http://localhost:8000/api/v1/users/me
```

## Example Usage

1. **Create a Super Admin** (via database or initial script)
2. **Login as Super Admin**
3. **Create Departments**
4. **Create Admin users and assign them to departments**
5. **Admins can create Managers in their departments**
6. **Managers can view/edit Students in their departments**

## Development

### Code Style
- Follow PEP 8
- Use type hints
- Async/await for all database operations

### Testing
```bash
# Run tests (when implemented)
pytest
```

## License

[Your License Here]

