# main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, conint, PositiveFloat
from datetime import datetime
from database import get_db, LoanApplication
from joblib import load
import traceback
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import pandas as pd
import os



app = FastAPI(title="Loan Fraud Detection API (Logistic Regression)")

# Load ML model
try:
    model = load("fraud_model.joblib")
    print("✅ ML Model loaded successfully!")
except Exception as e:
   print("❌ Error loading model:", e)

# -------------------------------
# Input schema
# -------------------------------
class LoanData(BaseModel):
    name: str
    age: conint(ge=18, le=100) # type: ignore
    income: PositiveFloat
    loan_amount: PositiveFloat
    purpose: str

    typing_speed: float | None = None
    avg_keypress_interval: float | None = None
    hesitation_time: float | None = None
    mouse_variance: float | None = None

# -------------------------------
# Root route
# -------------------------------
@app.get("/")
def home():
    return {"message": "Loan Fraud Backend is running with Logistic Regression!"}

# -------------------------------
# Submit route
# -------------------------------
@app.post("/submit")
def submit_loan(data: LoanData, db: Session = Depends(get_db)):
    try:
        # Prepare input
        input_dict = {
    "age": [data.age],
    "income": [data.income],
    "loan_amount": [data.loan_amount],
    "purpose": [data.purpose],
    # ---- Behavioral features (from frontend) ----
    "typing_speed": [data.typing_speed if data.typing_speed is not None else 0],
    "avg_keypress_interval": [data.avg_keypress_interval if data.avg_keypress_interval is not None else 0],
    "hesitation_time": [data.hesitation_time if data.hesitation_time is not None else 0],
    "mouse_variance": [data.mouse_variance if data.mouse_variance is not None else 0]
}


        import pandas as pd # type: ignore
        X_new = pd.DataFrame(input_dict)

        # Predict
        prob = model.predict_proba(X_new)[0][1]  # type: ignore # Probability of fraud
        prediction = "⚠️ Fraudulent" if prob > 0.5 else "✅ Legitimate"

        # Save to DB (ADD fraud_score here!)
        db_entry = LoanApplication(
            name=data.name,
            age=data.age,
            income=data.income,
            loan_amount=data.loan_amount,
            purpose=data.purpose,
            fraud_probability=round(float(prob), 3),
            prediction=prediction,
            fraud_score=round(float(prob), 3),  # ← ADD THIS LINE
            created_at=datetime.utcnow()
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)

        # Return response
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
# Get all applications
# -------------------------------
@app.get("/applications")
def get_all(db: Session = Depends(get_db)):
    apps = db.query(LoanApplication).order_by(LoanApplication.created_at.desc()).all()
    return {"total": len(apps), "applications": [
        {
            "id": a.id,
            "name": a.name,
            "age": a.age,
            "income": a.income,
            "loan_amount": a.loan_amount,
            "purpose": a.purpose,
            "fraud_probability": a.fraud_probability,
            "prediction": a.prediction,
            "fraud_score": a.fraud_score if a.fraud_score is not None else 0.0,  # ← CHANGE pred_prob to fraud_score
            "created_at": a.created_at.isoformat()
        } for a in apps
    ]}

@app.get("/health")
def health():
    return {"status": "healthy", "time": datetime.utcnow().isoformat()}
