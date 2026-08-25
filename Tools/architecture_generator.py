"""SIH Architecture Generator - Generates system architecture for SIH projects.

Generates:
- Frontend
- Backend
- API layer
- Authentication
- Database
- AI/ML
- Storage
- External APIs
- Notifications
- Admin dashboard
- Monitoring
- Deployment
- Hardware
- IoT
- Edge computing
- Offline architecture
- Security boundaries
- Data flow

Also stores the architecture as structured data.
Allows individual components to be edited or regenerated without destroying the complete architecture.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from Tools.sih_project_manager import SIHProjectManager

logger = logging.getLogger(__name__)


def generate_architecture(project_id: int, solution_description: str) -> Dict[str, Any]:
    """
    Generate a complete architecture for an SIH project.
    
    Args:
        project_id: The SIH project ID
        solution_description: Description of the solution
        
    Returns:
        Complete architecture dict with structured data
    """
    from Tools.sih_project_manager import SIHProjectManager
    from Tools.problem_statement_analyzer import analyze_problem_statement
    
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    
    # Analyze the problem to inform architecture
    analysis = analyze_problem_statement(project.get("problem_statement", "")) if project else {"extracted": {}}
    extracted = analysis.get("extracted", {})
    
    # Determine architecture type based on solution characteristics
    architecture_type = _determine_architecture_type(extracted)
    
    architecture = {
        "project_id": project_id,
        "solution_description": solution_description,
        "architecture_type": architecture_type,
        "generated_at": datetime.now().isoformat(),
        "frontend": _generate_frontend(architecture_type, extracted),
        "backend": _generate_backend(architecture_type, extracted),
        "api_layer": _generate_api_layer(architecture_type, extracted),
        "authentication": _generate_authentication(architecture_type, extracted),
        "database": _generate_database(architecture_type, extracted),
        "ai_ml": _generate_ai_ml(architecture_type, extracted),
        "storage": _generate_storage(architecture_type, extracted),
        "external_apis": _generate_external_apis(architecture_type, extracted),
        "notifications": _generate_notifications(architecture_type, extracted),
        "admin_dashboard": _generate_admin_dashboard(architecture_type, extracted),
        "monitoring": _generate_monitoring(architecture_type, extracted),
        "deployment": _generate_deployment(architecture_type, extracted),
        "hardware": _generate_hardware(architecture_type, extracted),
        "iot_edge": _generate_iot_edge(architecture_type, extracted),
        "security_boundaries": _generate_security_boundaries(architecture_type, extracted),
        "data_flow": _generate_data_flow(architecture_type, extracted),
    }
    
    # Save architecture to project
    _save_architecture_to_project(manager, project_id, architecture)
    
    manager.close()
    return architecture


def _determine_architecture_type(extracted: dict) -> str:
    """Determine the architecture type based on extracted problem elements."""
    # Check for AI/ML elements
    tech_reqs = extracted.get("technical_requirements", {})
    if tech_reqs.get("ai_ml"):
        return "ai_ml_focused"
    
    # Check for IoT/hardware elements
    if "hardware" in str(extracted).lower() or "iot" in str(extracted).lower():
        return "iot_edge"
    
    # Check for mobile app
    if "mobile" in str(extracted).lower() or "app" in str(extracted).lower():
        return "mobile_first"
    
    # Default web application architecture
    return "web_application"


def _generate_frontend(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate frontend architecture component."""
    if architecture_type == "mobile_first":
        return {
            "type": "React Native with Expo",
            "language": "JavaScript/TypeScript",
            "state_management": "Redux or Context API",
            "ui_library": "React Native Elements or Tailwind CSS",
            "offline_capability": "Async storage with sync on reconnection",
            "responsive": "Yes, mobile-first responsive design",
            "accessibility": "WCAG 2.1 AA compliant",
        }
    else:
        return {
            "type": "React with Next.js",
            "language": "JavaScript/TypeScript",
            "state_management": "Redux Toolkit or Context API",
            "ui_library": "Tailwind CSS or MUI",
            "ssr": "Next.js server-side rendering",
            "responsive": "Yes, fully responsive",
            "accessibility": "WCAG 2.1 AA compliant",
        }


def _generate_backend(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate backend architecture component."""
    if architecture_type == "ai_ml_focused":
        return {
            "type": "Node.js with Express",
            "language": "JavaScript/TypeScript",
            "framework": "Express.js",
            "api_framework": "NestJS or FastAPI",
            "auth_service": "JWT with refresh tokens",
            "scaling": "Horizontal scaling with load balancer",
            "container": "Docker with Kubernetes orchestration",
        }
    elif architecture_type == "iot_edge":
        return {
            "type": "Python with FastAPI",
            "language": "Python",
            "framework": "FastAPI",
            "auth_service": "OAuth2 with token-based auth",
            "scaling": "Async processing with message queue",
            "container": "Docker on edge devices",
        }
    else:
        return {
            "type": "Node.js with Express",
            "language": "JavaScript/TypeScript",
            "framework": "Express.js",
            "auth_service": "JWT with refresh tokens",
            "scaling": "Horizontal scaling with load balancer",
            "container": "Docker with simple deployment",
        }


def _generate_api_layer(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate API layer architecture component."""
    return {
        "type": "RESTful API with OpenAPI specification",
        "protocol": "HTTP/1.1 with JSON payloads",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/status", "description": "Service health check"},
            {"method": "POST", "path": "/api/v1/auth/login", "description": "User authentication"},
            {"method": "POST", "path": "/api/v1/data", "description": "Data submission"},
        ],
        "documentation": "Auto-generated with Swagger/OpenAPI",
        "rate_limiting": "Yes, 100 requests/minute per IP",
    }


def _generate_authentication(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate authentication architecture component."""
    return {
        "method": "JWT (JSON Web Tokens)",
        "provider": "Integrated auth service or OAuth 2.0",
        "tokens": "Access token (15 min) + Refresh token (7 days)",
        "social_login": "Google/GitHub optional",
        "password_policy": "Minimum 8 characters, mixed case, numbers, symbols",
        "2fa": "Optional SMS or authenticator app 2FA",
    }


def _generate_database(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate database architecture component."""
    # Determine based on data requirements
    return {
        "type": "PostgreSQL for relational data",
        "alternatives": ["MongoDB for document storage", "SQLite for embedded/local"],
        "orm": "Prisma or Sequelize",
        "migrations": "Alchemy or Fluent Migrator",
        "backup": "Daily automated backups",
        "retention": "90 days automatic, configurable",
        "access_control": "Role-based access control (RBAC)",
    }


def _generate_ai_ml(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate AI/ML architecture component."""
    if architecture_type == "ai_ml_focused":
        return {
            "type": "TensorFlow/PyTorch models",
            "model_deployment": "TensorFlow Serving or TorchServe",
            "api_integration": "REST API endpoints for predictions",
            "model_versions": "Versioned models with A/B testing",
            "training_pipeline": "CI/CD pipeline for model retraining",
            "monitoring": "Model drift detection and performance monitoring",
        }
    return {
        "type": "No AI/ML integration",
        "note": "AI/ML can be added later based on project requirements",
    }


def _generate_storage(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate storage architecture component."""
    return {
        "object_storage": "Amazon S3 or MinIO for file uploads",
        "session_storage": "Redis or Memcached for sessions",
        "cache": "Redis for frequently accessed data",
        "backup_strategy": "3-2-1 backup strategy (3 copies, 2 media, 1 off-site)",
        "encryption": "At-rest encryption with customer-managed keys",
    }


def _generate_external_apis(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate external APIs architecture component."""
    return {
        "mapping_apis": "Google Maps or OpenStreetMap API",
        "payment_gateways": "Stripe or Razorpay for payments",
        "notification_services": "Firebase Cloud Messaging or Twilio",
        "auth_providers": "Google/GitHub OAuth",
        "data_apis": "Open data portals or government APIs",
        "rate_limit_handling": "Yes, with exponential backoff",
    }


def _generate_notifications(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate notifications architecture component."""
    return {
        "method": "Firebase Cloud Messaging (FCM) or WebPush",
        "types": ["Push notifications", "Email notifications", "In-app messages"],
        "trigger_events": [
            "User registration",
            "Task completion",
            "System alerts",
            "Scheduled reminders",
        ],
        "delivery": "Reliable delivery with retry logic",
    }


def _generate_admin_dashboard(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate admin dashboard architecture component."""
    return {
        "type": "React admin dashboard with RBAC",
        "features": [
            "User management",
            "Project monitoring",
            "Analytics and reports",
            "System logs",
            "Settings configuration",
        ],
        "access": "Role-based (admin, editor, viewer)",
        "dashboard_library": "React Admin or Material-UI",
    }


def _generate_monitoring(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate monitoring architecture component."""
    return {
        "application monitoring": "Prometheus + Grafana",
        "error tracking": "Sentry or Bugsnag",
        "performance monitoring": "Lighthouse or Web Vitals",
        "logging": "Structured JSON logs to ELK or Loki",
        "alerts": "Email/SMS alerts for critical issues",
    }


def _generate_deployment(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate deployment architecture component."""
    if architecture_type == "ai_ml_focused":
        return {
            "platform": "AWS Elastic Beanstalk or Google Cloud Run",
            "ci_cd": "GitHub Actions or GitLab CI",
            "container": "Docker with multi-stage builds",
            "scaling": "Autoscaling based on CPU/memory metrics",
            "domain": "Custom domain with SSL certificate",
        }
    return {
        "platform": "Heroku or Vercel for frontend, Render for backend",
        "ci_cd": "GitHub Actions",
        "container": "Docker",
        "scaling": "Manual scaling or auto-limited",
        "domain": "Custom domain with free SSL",
    }


def _generate_hardware(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate hardware architecture component."""
    if architecture_type == "iot_edge":
        return {
            "devices": "Raspberry Pi 4 or similar SBC",
            "sensors": "DHT22 (temperature/humidity), BMP280 (pressure), camera module",
            "connectivity": "WiFi (ESP8266/ESP32) or cellular (SIM800)",
            "edge_processing": "TensorFlow Lite for microcontrollers",
            "power": "USB power or battery with 24h autonomy",
        }
    return {
        "devices": "Standard development devices (laptops, smartphones)",
        "sensors": "N/A (software-only)",
        "connectivity": "Internet via WiFi/cellular",
        "edge_processing": "N/A",
        "power": "Device battery/or power adapter",
    }


def _generate_iot_edge(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate IoT/Edge architecture component."""
    if architecture_type == "iot_edge":
        return {
            "architecture": "Two-tier edge-cloud architecture",
            "edge_layer": "TensorFlow Lite on Raspberry Pi for local processing",
            "cloud_layer": "AWS IoT Core or Azure IoT Hub for device management",
            "communication": "MQTT protocol over TLS for secure IoT communication",
            "data_processing": "Local preprocessing at edge, cloud analytics",
        }
    return {
        "architecture": "Standard client-server architecture",
        "note": "IoT/edge features can be added based on project requirements",
    }


def _generate_security_boundaries(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate security boundaries architecture component."""
    return {
        "network_segmentation": "VPC with public and private subnets",
        "data_encryption": "TLS 1.3 for transit, AES-256 at rest",
        "authentication": "JWT with refresh tokens, OAuth 2.0 providers",
        "authorization": "RBAC (Role-Based Access Control)",
        "input_validation": "Comprehensive input sanitization and XSS prevention",
        "audit_logging": "All actions logged with user attribution",
        "compliance": "GDPR considerations for data privacy",
    }


def _generate_data_flow(architecture_type: str, extracted: dict) -> Dict[str, Any]:
    """Generate data flow architecture component."""
    if architecture_type == "ai_ml_focused":
        return {
            "flow": "User input -> Frontend -> API Gateway -> ML Service -> Prediction -> Response -> Frontend",
            "data_stores": ["User sessions (Redis)", "Persistent data (PostgreSQL)", "Model artifacts (S3)"],
            "data_pipeline": "ETL pipeline with scheduled jobs",
            "data_privacy": "PII masked before storage, consent management",
        }
    return {
        "flow": "User input -> Frontend -> API -> Database -> Response -> Frontend",
        "data_stores": ["User sessions", "Persistent application data"],
        "data_pipeline": "Manual or scheduled data updates",
        "data_privacy": "Basic data privacy measures",
    }


def _save_architecture_to_project(manager: SIHProjectManager, project_id: int, architecture: Dict[str, Any]) -> None:
    """Save architecture to the project's permanent memory."""
    evidence_id = manager.add_evidence(
        project_id=project_id,
        title="System Architecture",
        e_type="architecture",
        path="",
        description=json.dumps(architecture, indent=2)
    )
    
    # Also add as a decision documenting the architecture choice
    manager.add_decision(
        project_id=project_id,
        decision="System architecture designed and documented",
        alternatives=[
            "Monolithic architecture",
            "Microservices architecture",
            "Serverless architecture",
        ],
        reason="Selected based on project requirements, scalability needs, and development timeline",
        evidence=f"Evidence ID: {evidence_id}",
    )
    
    manager.close()


def edit_architecture_component(project_id: int, component: str, updates: Dict[str, Any]) -> bool:
    """
    Edit a specific architecture component without destroying the complete architecture.
    
    Args:
        project_id: The SIH project ID
        component: The component to edit (e.g., "frontend", "backend", "database")
        updates: Dict of updates to apply
        
    Returns:
        True if successful, False otherwise
    """
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    
    # Get current architecture
    architecture = manager.select_project(project_id)
    if not architecture:
        manager.close()
        return False
    
    current_arch = architecture.get("architecture", {})
    if not current_arch:
        manager.close()
        return False
    
    # Update the specified component
    if component in current_arch:
        current_arch[component].update(updates)
        # Save updated architecture
        manager.add_evidence(
            project_id=project_id,
            title="Architecture Component Update",
            e_type="architecture_edit",
            path="",
            description=f"Updated {component} component: {json.dumps(updates, indent=2)}"
        )
        manager.close()
        return True
    
    manager.close()
    return False


def get_architecture(project_id: int) -> Optional[Dict[str, Any]]:
    """Get architecture for a project."""
    from Tools.sih_project_manager import SIHProjectManager
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    if project and "architecture" in project:
        return project["architecture"]
    manager.close()
    return None


def mvp_planner(project_id: int) -> Dict[str, Any]:
    """
    MVP Planner - Automatically classify features into priority categories.
    
    Classifies features into:
    - MUST HAVE: Core functionality required for the solution
    - SHOULD HAVE: Important features that improve the product
    - NICE TO HAVE: Optional features
    - DEMO IMPACT: Features that significantly improve the live demonstration
    - FUTURE SCOPE: Features that should not consume hackathon development time
    
    For every feature shows:
    - Priority
    - Estimated effort
    - Dependencies
    - Owner
    - Status
    - Risk
    """
    from Tools.sih_project_manager import SIHProjectManager
    from Tools.problem_statement_analyzer import analyze_problem_statement
    
    manager = SIHProjectManager()
    project = manager.select_project(project_id)
    
    if not project:
        manager.close()
        return {"error": f"Project ID {project_id} not found"}
    
    # Get existing features
    features = manager.list_features(project_id)
    
    # Analyze problem statement for MUST HAVE criteria
    analysis = analyze_problem_statement(project.get("problem_statement", ""))
    extracted = analysis.get("extracted", {})
    
    # Classify features
    classified_features = []
    
    for feature in features:
        title = feature.get("title", "")
        priority = "NICE TO HAVE"  # default
        estimated_effort = feature.get("estimated_effort", "Unknown")
        dependencies = feature.get("dependencies", "")
        owner = feature.get("owner", "Unassigned")
        status = feature.get("status", "pending")
        risk = "Medium"
        
        # CLASSIFICATION LOGIC
        # MUST HAVE: Core functionality
        if any(kw in title.lower() for kw in ["core", "essential", "primary", "main", "basic"]):
            priority = "MUST HAVE"
        # SHOULD HAVE: Important but not critical
        elif any(kw in title.lower() for kw in ["important", "should", "recommended", "beneficial"]):
            priority = "SHOULD HAVE"
        # DEMO IMPACT: Features that demo well
        elif any(kw in title.lower() for kw in ["demo", "showcase", "presentation", "demonstration"]):
            priority = "DEMO IMPACT"
        # FUTURE SCOPE: Nice but not now
        elif any(kw in title.lower() for kw in ["future", "later", "phase 2", "enhancement"]):
            priority = "FUTURE SCOPE"
        # MUST HAVE if no core features defined but problem statement exists
        elif not any(kw in title.lower() for kw in ["future", "later", "phase 2", "enhancement", "nice"]):
            # If it's a core concept from the problem statement
            problem_keywords = extracted.get("required_solution", [])
            if any(kw.lower() in title.lower() for kw in problem_keywords):
                priority = "MUST HAVE"
        
        # Adjust risk based on priority
        if priority == "MUST HAVE":
            risk = "Low - critical path"
        elif priority == "SHOULD HAVE":
            risk = "Medium"
        elif priority == "DEMO IMPACT":
            risk = "Low - demo-focused"
        else:
            risk = "High - can be deferred"
        
        classified_features.append({
            "title": title,
            "priority": priority,
            "estimated_effort": estimated_effort,
            "dependencies": dependencies,
            "owner": owner,
            "status": status,
            "risk": risk,
        })
    
    # If no features exist, create default classification based on problem analysis
    if not classified_features:
        # Create default features based on problem statement analysis
        problem = project.get("problem_statement", "")[:200] if project else ""
        classified_features = [
            {
                "title": "Core solution functionality",
                "priority": "MUST HAVE",
                "estimated_effort": "4-6 weeks",
                "dependencies": "Problem analysis, requirements",
                "owner": "Team lead",
                "status": "pending",
                "risk": "Low - critical path",
            },
            {
                "title": "User authentication",
                "priority": "MUST HAVE",
                "estimated_effort": "1-2 weeks",
                "dependencies": "User management system",
                "owner": "Backend developer",
                "status": "pending",
                "risk": "Low",
            },
            {
                "title": "Basic UI/UX",
                "priority": "SHOULD HAVE",
                "estimated_effort": "2-3 weeks",
                "dependencies": "Design assets, user research",
                "owner": "Frontend developer",
                "status": "pending",
                "risk": "Medium",
            },
            {
                "title": "Admin dashboard",
                "priority": "NICE TO HAVE",
                "estimated_effort": "2-4 weeks",
                "dependencies": "Backend APIs, user management",
                "owner": "Fullstack developer",
                "status": "pending",
                "risk": "Low",
            },
            {
                "title": "Analytics and reporting",
                "priority": "DEMO IMPACT",
                "estimated_effort": "1-2 weeks",
                "dependencies": "Data collection, database",
                "owner": "Data analyst",
                "status": "pending",
                "risk": "Low",
            },
            {
                "title": "Future enhancements",
                "priority": "FUTURE SCOPE",
                "estimated_effort": "4+ weeks",
                "dependencies": "Core features completed, user feedback",
                "owner": "Product manager",
                "status": "pending",
                "risk": "High - can be deferred",
            },
        ]
    
    manager.close()
    return {
        "project_id": project_id,
        "classified_features": classified_features,
        "classification_date": datetime.now().isoformat(),
        "methodology": "Automated classification based on problem statement analysis and feature keywords",
    }