# main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, conint, PositiveFloat, EmailStr
from datetime import datetime
from database import get_db, LoanApplication
from joblib import load
import traceback
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI(title="Loan Fraud Detection API (Logistic Regression)")

# -------------------------------
# CORS Middleware
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Load ML model
# -------------------------------
try:
    model = load("fraud_model.joblib")
    print("✅ ML Model loaded successfully!")
except Exception as e:
    print("❌ Error loading model:", e)

# -------------------------------
# Input schema for ML endpoint
# -------------------------------
class LoanData(BaseModel):
    name: str
    age: conint(ge=18, le=100)  # type: ignore
    income: PositiveFloat
    loan_amount: PositiveFloat
    purpose: str

    typing_speed: float | None = None
    avg_keypress_interval: float | None = None
    hesitation_time: float | None = None
    mouse_variance: float | None = None

# -------------------------------
# Input schema for education loan frontend endpoint
# -------------------------------
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, PositiveFloat, validator, Field

class EducationLevel(str, Enum):
    UNDERGRADUATE = "undergraduate"
    POSTGRADUATE = "postgraduate"
    DOCTORATE = "doctorate"
    OTHER = "other"

class LoanPurpose(str, Enum):
    TUITION_FEE = "tuition_fee"
    LIVING_EXPENSES = "living_expenses"
    EQUIPMENT = "study_equipment"
    FULL_PACKAGE = "tuition_and_living_expenses"

class FrontendLoanData(BaseModel):
    name: str
    age: int = Field(..., ge=16, le=65)  # Modified age range for education loans
    college: str  # Prospective college/university
    education_level: EducationLevel
    total_course_fee: PositiveFloat  # User provides total tuition for the entire course
    loan_amount: PositiveFloat
    income: PositiveFloat
    income_proof: str
    email: EmailStr
    phone: str
    purpose: LoanPurpose
    
    # Optional co-signer information for students with low income
    cosigner_name: Optional[str] = None
    cosigner_income: Optional[PositiveFloat] = None
    
    # Optional behavioral fields
    typing_speed: Optional[float] = None
    avg_keypress_interval: Optional[float] = None
    hesitation_time: Optional[float] = None
    mouse_variance: Optional[float] = None
    
    @validator('loan_amount')
    def validate_loan_amount(cls, v, values):
        if 'semester_fee' in values and v > (values['semester_fee'] * values['course_duration'] * 2):
            raise ValueError("Loan amount cannot exceed twice the total course fee")
        return v

    @validator('cosigner_income')
    def validate_cosigner_income(cls, v, values):
        if 'income' in values and values['income'] < 30000 and (v is None or v < 50000):
            raise ValueError("Co-signer with income above 50,000 required for applicants with low income")
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "age": 20,
                "college": "State University",
                "education_level": "undergraduate",
                "course_duration": 4,
                "semester_fee": 15000,
                "loan_amount": 120000,
                "income": 5000,
                "income_proof": "No",
                "email": "john.doe@example.com",
                "phone": "1234567890",
                "purpose": "tuition_fee",
                "cosigner_name": "Jane Doe",
                "cosigner_income": 75000
            }
        }

# -------------------------------
# Root route
# -------------------------------
@app.get("/")
def home():
    return {"message": "Loan Fraud Backend is running with Logistic Regression!"}

# -------------------------------
# ML-based submit route
# -------------------------------
@app.post("/submit")
def submit_loan(data: LoanData, db: Session = Depends(get_db)):
    try:
        input_dict = {
            "age": [data.age],
            "income": [data.income],
            "loan_amount": [data.loan_amount],
            "purpose": [data.purpose],
            "typing_speed": [data.typing_speed if data.typing_speed is not None else 0],
            "avg_keypress_interval": [data.avg_keypress_interval if data.avg_keypress_interval is not None else 0],
            "hesitation_time": [data.hesitation_time if data.hesitation_time is not None else 0],
            "mouse_variance": [data.mouse_variance if data.mouse_variance is not None else 0]
        }

        X_new = pd.DataFrame(input_dict)
        prob = model.predict_proba(X_new)[0][1]  # Probability of fraud
        prediction = "⚠️ Fraudulent" if prob > 0.5 else "✅ Legitimate"

        # Save to DB
        db_entry = LoanApplication(
            name=data.name,
            age=data.age,
            income=data.income,
            loan_amount=data.loan_amount,
            purpose=data.purpose,
            fraud_probability=round(float(prob), 3),
            prediction=prediction,
            fraud_score=round(float(prob), 3),
            created_at=datetime.utcnow()
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)

        return {
            "id": db_entry.id,
            "name": data.name,
            "fraud_probability": round(float(prob), 3),
            "prediction": prediction,
            "message": "Loan application processed successfully!"
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# -------------------------------
# Frontend-friendly route (JS form) - FIXED
# -------------------------------
@app.post("/apply-loan-frontend")
def apply_loan_frontend(data: FrontendLoanData, db: Session = Depends(get_db)):
    # Phone number validation: must be exactly 10 digits
    if not (data.phone.isdigit() and len(data.phone) == 10):
        raise HTTPException(status_code=400, detail="Phone number must be exactly 10 digits.")

    # Error handling for unique constraint violations
    from sqlalchemy.exc import IntegrityError
    try:
        # ...existing risk logic and response...
        # Save to DB (with phone/email)
        db_entry = LoanApplication(
            name=data.name,
            age=data.age,
            income=data.income,
            loan_amount=data.loan_amount,
            purpose=data.purpose.value if hasattr(data.purpose, 'value') else str(data.purpose),
            email=data.email,
            phone=data.phone,
            fraud_probability=None,
            prediction=None,
            fraud_score=score,
            created_at=datetime.utcnow()
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError as e:
        db.rollback()
        # Check which field caused the error
        if "phone" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Duplicate phone number. Application already exists.")
        elif "email" in str(e.orig).lower():
            raise HTTPException(status_code=400, detail="Duplicate Gmail. Application already exists.")
        else:
            raise HTTPException(status_code=400, detail="Duplicate entry. Application already exists.")
    """
    Enhanced fraud scoring endpoint with comprehensive risk assessment.
    """
    score = 0
    reasons = []
    recommendations = []
    risk_factors = {}

    # 1. Financial Risk Assessment
        # For education loans, focus on tuition fee and loan amount difference
        # Use only one income source: either student or cosigner
        if data.cosigner_income:
            effective_income = data.cosigner_income
            risk_factors["income_source"] = "cosigner"
        else:
            effective_income = data.income
            risk_factors["income_source"] = "student"

        # Tuition fee total for the course (user provided)
        tuition_loan_diff = data.loan_amount - data.total_course_fee
        risk_factors["tuition_loan_diff"] = tuition_loan_diff

        # If loan amount exceeds tuition fee by a large margin, flag for review
        if tuition_loan_diff > 50000:
            score += 30
            reasons.append(f"Loan amount exceeds total tuition fee by {tuition_loan_diff:,.0f}. Please justify additional expenses.")
            recommendations.append("Provide breakdown for living expenses, equipment, or other costs.")

        # Moratorium period: no repayment during course + 12 months after graduation
        moratorium_months = data.course_duration * 12 + 12
        repayment_years = 5  # Typical repayment period after moratorium
        annual_interest_rate = 0.1
        monthly_interest_rate = annual_interest_rate / 12
        n_payments = repayment_years * 12
        # EMI formula: P * r * (1 + r)^n / ((1 + r)^n - 1)
        if monthly_interest_rate > 0:
            emi = data.loan_amount * monthly_interest_rate * (1 + monthly_interest_rate) ** n_payments / ((1 + monthly_interest_rate) ** n_payments - 1)
        else:
            emi = data.loan_amount / n_payments
        risk_factors["expected_emi"] = round(emi, 2)

        # Use cosigner income for DTI
        monthly_income = effective_income / 12
        dti_ratio = (emi / monthly_income) * 100 if monthly_income > 0 else 0
        risk_factors["dti_ratio"] = round(dti_ratio, 2)

        if dti_ratio > 50:
            score += 40
            reasons.append(f"Expected EMI after moratorium would be {dti_ratio:.1f}% of monthly income (should be below 50%)")
            recommendations.append("Consider a smaller loan amount or provide additional income sources/cosigner")
        elif dti_ratio > 30:
            score += 20
            reasons.append(f"Expected EMI after moratorium would be {dti_ratio:.1f}% of monthly income (recommended: below 30%)")
            recommendations.append("Consider a smaller loan amount for better approval chances")

    # Minimum Income Threshold (adjusted by loan amount)
    min_income = max(30000, data.loan_amount * 0.2)  # At least 30k or 20% of loan amount
    if data.income < min_income:
        score += 30
        reasons.append(f"Annual income ({data.income:,.0f}) is below minimum requirement ({min_income:,.0f})")
        recommendations.append("Need higher income or a co-signer")
        risk_factors["income_ratio"] = data.income / min_income

    # Education Loan Purpose Assessment
    if data.purpose == LoanPurpose.FULL_PACKAGE:
        # Higher scrutiny for full package loans
        if data.loan_amount > 200000:
            score += 15
            reasons.append("Large full package loan amount requires additional verification")
            recommendations.append("Please provide detailed breakdown of tuition and living expenses")
    elif data.purpose == LoanPurpose.LIVING_EXPENSES:
        # Stricter limits on living expenses
        max_living_expenses = 50000 * data.course_duration
        if data.loan_amount > max_living_expenses:
            score += 20
            reasons.append(f"Living expenses loan amount exceeds maximum limit of {max_living_expenses:,}")
            recommendations.append("Consider reducing living expenses loan amount")
    elif data.purpose == LoanPurpose.EQUIPMENT:
        # Equipment loans should be relatively small
        if data.loan_amount > 20000:
            score += 10
            reasons.append("Equipment loan amount seems high")
            recommendations.append("Please provide list of required equipment with costs")
    
    # Education loan specific checks
    if data.loan_amount > 100000:
        score += 10
        reasons.append("High education loan amount - requires additional verification")
        recommendations.append("Provide detailed education cost breakdown")
    
    # Verify college information
    if not data.college or len(data.college.strip()) == 0:
        score += 20
        reasons.append("Prospective College/University name is required")
        recommendations.append("Provide name of the institution you're planning to attend")
    
    # Add note about provisional approval
    recommendations.append("Note: This is a provisional approval. Final loan disbursement will require admission confirmation")
    
    # Education-specific DTI considerations for students
    if data.age < 25:  # Typical student age
        # More lenient DTI for students
        if dti_ratio > 70:  # Adjusted from 50 for students
            score += 30
            reasons.append(f"Even for student loans, monthly payment of {dti_ratio:.1f}% of income is too high")
            recommendations.append("Consider applying with a co-signer or provide proof of future employment")

    # Documentation and Verification
    if data.income_proof == "No":
        score += 30
        reasons.append("No income proof provided")
        recommendations.append("Submit recent pay stubs or tax returns")

    if not data.college_id or len(data.college_id.strip()) == 0:
        score += 10
        reasons.append("College ID missing or invalid")
        recommendations.append("Provide valid college identification")

    # Behavioral Scoring (if available)
    if all(x is not None for x in [data.typing_speed, data.avg_keypress_interval, 
                                  data.hesitation_time, data.mouse_variance]):
        # Suspicious patterns
        if data.typing_speed > 200 or data.typing_speed < 10:
            score += 5
            reasons.append("Unusual typing pattern detected")
        if data.hesitation_time > 10:
            score += 5
            reasons.append("Excessive hesitation in form filling")
        risk_factors["behavioral_score"] = sum([
            1 if data.typing_speed > 200 or data.typing_speed < 10 else 0,
            1 if data.hesitation_time > 10 else 0,
            1 if data.mouse_variance > 100 else 0
        ])

    # Cap score at 100
    if score > 100:
        score = 100

    # Determine Risk Level and Status
    if score <= 20:
        risk_level = "Low Risk"
        status = "Approved"
    elif score <= 40:
        risk_level = "Moderate Risk"
        status = "Approved with Conditions"
    elif score <= 70:
        risk_level = "High Risk"
        status = "Pending Additional Verification"
    else:
        risk_level = "Very High Risk"
        status = "Rejected"

    return {
        "fraud_score": score,
        "status": status,
        "risk_level": risk_level,
        "reasons": reasons,
        "recommendations": recommendations,
        "risk_factors": risk_factors
    }

# -------------------------------
# Get all applications
# -------------------------------
@app.get("/applications")
def get_all(db: Session = Depends(get_db)):
    apps = db.query(LoanApplication).order_by(LoanApplication.created_at.desc()).all()
    return {
        "total": len(apps),
        "applications": [
            {
                "id": a.id,
                "name": a.name,
                "age": a.age,
                "income": a.income,
                "loan_amount": a.loan_amount,
                "purpose": a.purpose,
                "email": getattr(a, "email", None),
                "phone": getattr(a, "phone", None),
                "fraud_probability": a.fraud_probability,
                "prediction": a.prediction,
                "fraud_score": a.fraud_score if a.fraud_score is not None else 0.0,
                "created_at": a.created_at.isoformat()
            } for a in apps
        ]
    }

# -------------------------------
# Health check
# -------------------------------
@app.get("/health")
def health():
    return {"status": "healthy", "time": datetime.utcnow().isoformat()}